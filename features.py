"""
Real places a journey stop can land on: woods for Lothlórien, wetland for
the Dead Marshes, a tunnel or underpass for Moria.

Bridges and tunnels come straight from the walk graph's edge tags. Every
other terrain needs OSM features (woods, water, parks and so on) that the
walk network doesn't include. Those are downloaded on demand around where
someone walks, cached to disk per ~5km grid cell, and kept in memory once
loaded. Like city maps (regions.py), a download runs in a background
thread, and routes fall back to plain stop placement until it's ready.
"""
import math
import pickle
import threading
import time
from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox
import shapely
from shapely.strtree import STRtree

FEATURE_DIR = Path(__file__).parent / "cache" / "features"
CELL_DEG = 0.05        # cache cell size, about 5km
FETCH_RADIUS_M = 10000  # around a cell's center: covers walks starting anywhere in it

# OSM tags for each terrain, and what to try when none is nearby.
# Edge terrains (bridge, tunnel) come from the walk graph instead of tags.
TERRAINS = {
    "forest": {"tags": {"natural": ["wood"], "landuse": ["forest"]}, "fallback": ["park"]},
    "water": {
        "tags": {"natural": ["water", "beach"], "waterway": ["river", "stream", "canal"]},
        "fallback": ["marsh", "bridge", "park"],
    },
    "marsh": {"tags": {"natural": ["wetland"]}, "fallback": ["water", "meadow"]},
    "meadow": {
        "tags": {"landuse": ["meadow"], "natural": ["grassland", "heath", "scrub"]},
        "fallback": ["park"],
    },
    "park": {"tags": {"leisure": ["park", "garden", "nature_reserve"]}, "fallback": []},
    "town": {"tags": {"landuse": ["commercial", "retail"], "amenity": ["marketplace"]}, "fallback": ["park"]},
    "hill": {"tags": {"natural": ["peak", "hill"]}, "fallback": ["tower", "forest", "park"]},
    "tower": {
        "tags": {"man_made": ["tower"], "historic": ["castle", "ruins", "monument"]},
        "fallback": ["town", "park"],
    },
    "bridge": {"edge": "bridge", "fallback": ["water", "park"]},
    "tunnel": {"edge": "tunnel", "fallback": ["bridge", "forest", "park"]},
}

# A node counts as "at" a feature within this distance of it, in meters.
NEAR_POLYGON_M = 30
NEAR_LINE_M = 40   # rivers and streams
NEAR_POINT_M = 75  # peaks, towers, monuments

PREPARING, READY, FAILED = "preparing", "ready", "failed"


def terrain_order(terrain):
    """The terrain followed by its fallbacks, without repeats."""
    order = [terrain] + TERRAINS[terrain]["fallback"]
    return list(dict.fromkeys(order))


def all_tags():
    tags = {}
    for spec in TERRAINS.values():
        for key, values in spec.get("tags", {}).items():
            tags.setdefault(key, set()).update(values)
    return {k: sorted(v) for k, v in tags.items()}


def classify(row):
    """Terrains an OSM feature row belongs to (a beach can be both water and park, etc.)."""
    terrains = []
    for terrain, spec in TERRAINS.items():
        for key, values in spec.get("tags", {}).items():
            value = row.get(key)
            if isinstance(value, str) and value in values:
                terrains.append(terrain)
                break
    return terrains


def fetch_features(lat, lon, radius_m=FETCH_RADIUS_M, retry_waits=(15, 30, 60)):
    """
    Download features from OSM as [{"terrain", "name", "geometry"}] in lon/lat.
    The public Overpass API often answers "at capacity"; it asks clients to
    retry with exponential backoff, so this does.
    """
    ox.settings.requests_timeout = 180
    for wait in (*retry_waits, None):
        try:
            gdf = ox.features_from_point((lat, lon), tags=all_tags(), dist=radius_m)
            break
        except Exception:
            if wait is None:
                raise
            time.sleep(wait)
    features = []
    for _, row in gdf.iterrows():
        name = row.get("name")
        name = name if isinstance(name, str) else None
        for terrain in classify(row):
            features.append({"terrain": terrain, "name": name, "geometry": row.geometry})
    return features


def cell_for(lat, lon):
    """Cache cell id and its center for a point."""
    i, j = math.floor(lat / CELL_DEG), math.floor(lon / CELL_DEG)
    center = ((i + 0.5) * CELL_DEG, (j + 0.5) * CELL_DEG)
    return f"{i}_{j}", center


class Cell:
    def __init__(self, id, center):
        self.id = id
        self.center = center
        self.status = PREPARING
        self.error = None
        self.features = None

    def info(self):
        return {"id": self.id, "status": self.status, "error": self.error}


class FeatureStore:
    def __init__(self, fetch_fn=fetch_features, feature_dir=FEATURE_DIR, background=True):
        self.fetch_fn = fetch_fn
        self.feature_dir = Path(feature_dir)
        self.background = background
        self.cells = {}
        self.lock = threading.Lock()

    def ensure(self, lat, lon):
        """The cell covering (lat, lon), starting its download or disk load if needed."""
        cell_id, center = cell_for(lat, lon)
        with self.lock:
            cell = self.cells.get(cell_id)
            if cell is not None and cell.status != FAILED:
                return cell
            cell = Cell(cell_id, center)
            self.cells[cell_id] = cell
        if self.background:
            threading.Thread(target=self._prepare, args=(cell,), daemon=True).start()
        else:
            self._prepare(cell)
        return cell

    def get(self, cell_id):
        return self.cells.get(cell_id)

    def ready_features(self, lat, lon):
        """Features for a point if its cell is ready, else None (and start getting it ready)."""
        cell = self.ensure(lat, lon)
        return cell.features if cell.status == READY else None

    def _prepare(self, cell):
        path = self.feature_dir / f"{cell.id}.pkl"
        try:
            if path.exists():
                with open(path, "rb") as f:
                    features = pickle.load(f)
            else:
                features = self.fetch_fn(cell.center[0], cell.center[1], FETCH_RADIUS_M)
                self.feature_dir.mkdir(parents=True, exist_ok=True)
                with open(path, "wb") as f:
                    pickle.dump(features, f)
            cell.features = features
            cell.status = READY
        except Exception as e:
            cell.status = FAILED
            cell.error = f"Couldn't load nearby places: {e}"


def find_anchors(G, features, near_nodes):
    """
    Which of near_nodes sit at a real place of each terrain.
    Returns {terrain: {node: place_name or None}}.

    Feature and node coordinates are projected to local meters around the
    nodes' center (fine at walk scale), then each terrain's features go in
    an STRtree and are queried for nodes within the "near" distance.
    """
    near_nodes = list(near_nodes)
    anchors = {terrain: {} for terrain in TERRAINS}
    if not near_nodes:
        return anchors

    # Edge terrains straight from the graph
    # (only edges touching nearby nodes, not the whole regional graph)
    for n in near_nodes:
        for nb, data in G[n].items():
            for terrain in ("bridge", "tunnel"):
                if data.get(terrain):
                    anchors[terrain].setdefault(n, data.get("name"))
                    anchors[terrain].setdefault(nb, data.get("name"))

    if not features:
        return anchors

    xs = np.array([G.nodes[n]["x"] for n in near_nodes])
    ys = np.array([G.nodes[n]["y"] for n in near_nodes])
    lon0, lat0 = xs.mean(), ys.mean()
    kx = 111320 * math.cos(math.radians(lat0))
    ky = 110540

    def to_m(coords):
        return np.column_stack(((coords[:, 0] - lon0) * kx, (coords[:, 1] - lat0) * ky))

    points = shapely.points(to_m(np.column_stack((xs, ys))))

    by_terrain = {}
    for f in features:
        geom = shapely.transform(f["geometry"], to_m)
        # Pad points and lines so one "within NEAR_POLYGON_M" query covers every shape
        kind = geom.geom_type
        if kind in ("Point", "MultiPoint"):
            geom = geom.buffer(NEAR_POINT_M - NEAR_POLYGON_M)
        elif kind in ("LineString", "MultiLineString"):
            geom = geom.buffer(NEAR_LINE_M - NEAR_POLYGON_M)
        by_terrain.setdefault(f["terrain"], []).append((geom, f["name"]))

    for terrain, items in by_terrain.items():
        tree = STRtree([g for g, _ in items])
        point_idx, feature_idx = tree.query(points, predicate="dwithin", distance=NEAR_POLYGON_M)
        for p, fi in zip(point_idx, feature_idx):
            node = near_nodes[p]
            name = items[fi][1]
            # Prefer a named feature when a node touches several
            if anchors[terrain].get(node) is None:
                anchors[terrain][node] = name
    return anchors


def nodes_within(G, start_node, radius_m):
    """Nodes reachable from start_node within radius_m of walking."""
    return nx.single_source_dijkstra_path_length(G, start_node, cutoff=radius_m, weight="length").keys()
