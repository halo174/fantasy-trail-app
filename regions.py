"""
Map regions the app can route in.

Madison's 50-mile graph is loaded at startup and always stays in memory.
Any other US city gets a small walk network pulled from OpenStreetMap the
first time someone picks it, in a background thread since a pull takes
anywhere from a few seconds to a couple of minutes. Pulled networks are
saved to cache/regions/ so each city is only ever pulled once, and only a
few are kept in memory at a time.
"""
import math
import threading
import time
from pathlib import Path

import osmnx as ox
import requests

from graph_utils import to_simple_graph, get_bridges

REGION_DIR = Path(__file__).parent / "cache" / "regions"

# A 6km radius covers a city's core and supports walks up to about 12km.
# Bigger pulls get slow and unreliable on the public Overpass API.
PULL_RADIUS_M = 6000
PULLED_MAX_TARGET_M = 12000
MAX_LOADED = 3  # pulled regions kept in memory, besides the permanent ones

# Nominatim's usage policy asks for an app-identifying User-Agent and at
# most one request per second.
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "fantasy-trail-app/0.1"

PREPARING, READY, FAILED, STORED = "preparing", "ready", "failed", "stored"


def haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def pull_walk_network(lat, lon, radius_m):
    ox.settings.requests_timeout = 180
    return ox.graph_from_point((lat, lon), dist=radius_m, network_type="walk")


_geocode_lock = threading.Lock()
_last_geocode = 0.0
_geocode_cache = {}


def geocode_us(query):
    """Up to 5 US places matching query, as [{"name", "lat", "lon"}]."""
    global _last_geocode
    key = query.strip().lower()
    if key in _geocode_cache:
        return _geocode_cache[key]
    with _geocode_lock:
        wait = 1.0 - (time.monotonic() - _last_geocode)
        if wait > 0:
            time.sleep(wait)
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "countrycodes": "us", "format": "jsonv2", "limit": 5, "addressdetails": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        _last_geocode = time.monotonic()
    resp.raise_for_status()
    results = []
    for item in resp.json():
        state = item.get("address", {}).get("state")
        name = item.get("name") or item["display_name"].split(",")[0]
        results.append({
            "name": f"{name}, {state}" if state else name,
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
        })
    _geocode_cache[key] = results
    return results


class Region:
    def __init__(self, id, name, lat, lon, radius_m, max_target_m=None, permanent=False):
        self.id = id
        self.name = name
        self.lat = lat
        self.lon = lon
        self.radius_m = radius_m
        self.max_target_m = max_target_m
        self.permanent = permanent
        self.status = PREPARING
        self.error = None
        self.G_multi = None
        self.G = None
        self.last_used = time.monotonic()

    def contains(self, lat, lon, margin_m=0):
        return haversine_m(self.lat, self.lon, lat, lon) + margin_m <= self.radius_m

    def info(self):
        return {
            "id": self.id, "name": self.name, "lat": self.lat, "lon": self.lon,
            "radius_m": self.radius_m, "max_target_m": self.max_target_m,
            # A stored region reloads from disk on its next route request
            "status": READY if self.status == STORED else self.status,
            "error": self.error,
        }


class RegionNotReady(Exception):
    pass


class RegionStore:
    def __init__(self, pull_fn=pull_walk_network, region_dir=REGION_DIR,
                 max_loaded=MAX_LOADED, background=True):
        self.pull_fn = pull_fn
        self.region_dir = Path(region_dir)
        self.max_loaded = max_loaded
        self.background = background  # tests run preparation inline
        self.regions = {}
        self.lock = threading.Lock()

    def add_permanent(self, id, name, lat, lon, radius_m, G_multi, G):
        region = Region(id, name, lat, lon, radius_m, permanent=True)
        region.G_multi, region.G, region.status = G_multi, G, READY
        self.regions[id] = region
        return region

    def get(self, region_id):
        return self.regions.get(region_id)

    def ensure_region(self, lat, lon, name):
        """
        The region to use for a city centered at (lat, lon). Reuses a region
        that already covers the whole city, otherwise loads it from the disk
        cache or pulls it from OSM in the background. Check .status.
        """
        with self.lock:
            for region in self.regions.values():
                if region.status != FAILED and region.contains(lat, lon, margin_m=PULL_RADIUS_M):
                    return region

            region_id = f"{lat:.3f}_{lon:.3f}"
            region = self.regions.get(region_id)
            if region is not None and region.status != FAILED:
                return region
            region = Region(region_id, name, lat, lon, PULL_RADIUS_M, max_target_m=PULLED_MAX_TARGET_M)
            self.regions[region_id] = region

        self._start_preparing(region)
        return region

    def get_for_route(self, region_id):
        """A ready region with its graph in memory, reloading it from disk if it was evicted."""
        region = self.regions.get(region_id)
        if region is None:
            raise KeyError(region_id)
        if region.status == STORED:
            region.status = PREPARING
            self._prepare(region)  # inline: a small graph from disk takes a few seconds
        if region.status != READY:
            raise RegionNotReady(region.error or region.status)
        region.last_used = time.monotonic()
        return region

    def _path(self, region):
        return self.region_dir / f"{region.id}.graphml"

    def _start_preparing(self, region):
        if self.background:
            threading.Thread(target=self._prepare, args=(region,), daemon=True).start()
        else:
            self._prepare(region)

    def _prepare(self, region):
        try:
            path = self._path(region)
            if path.exists():
                G_multi = ox.load_graphml(path)
            else:
                G_multi = self.pull_fn(region.lat, region.lon, region.radius_m)
                self.region_dir.mkdir(parents=True, exist_ok=True)
                ox.save_graphml(G_multi, filepath=path)
            G = to_simple_graph(G_multi)
            get_bridges(G)
            region.G_multi, region.G = G_multi, G
            region.error = None
            region.status = READY
            region.last_used = time.monotonic()
            self._evict()
        except Exception as e:
            region.status = FAILED
            region.error = f"Couldn't load the map for {region.name}: {e}"

    def _evict(self):
        """Drop the least recently used pulled graphs beyond max_loaded. They stay on disk."""
        with self.lock:
            loaded = [r for r in self.regions.values() if not r.permanent and r.status == READY]
            loaded.sort(key=lambda r: r.last_used)
            for region in loaded[:max(0, len(loaded) - self.max_loaded)]:
                region.G_multi = region.G = None
                region.status = STORED
