from contextlib import asynccontextmanager
from pathlib import Path

import osmnx as ox
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pathfinding import find_path_with_restarts, within_tolerance, UnreachableError
from graph_utils import to_simple_graph, highway_breakdown, get_bridges, points_along_path, TRAIL_TYPES
from journeys import JOURNEYS, JOURNEYS_BY_ID
from regions import RegionStore, RegionNotReady, geocode_us

STATIC_DIR = Path(__file__).parent / "static"
MADISON_ID = "madison"

state = {}

# Loops do best with many short attempts. Benchmarked on 3-20km loops from an
# Arboretum and an urban start: 5000x40 found 49/50 within tolerance, vs 41/50
# for 20000x10, at similar or lower latency (median under 0.7s even at 20km).
LOOP_SEARCH = {"steps_per_attempt": 5000, "max_restarts": 40}
POINT_TO_POINT_SEARCH = {"max_restarts": 3}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading graph...")
    G_multi = ox.load_graphml("madison_50mi_tiled_walk_network.graphml")
    G = to_simple_graph(G_multi)
    print("Finding bridges for loop routing...")
    get_bridges(G)  # ~6s, cached on the graph so loop requests don't pay it
    store = RegionStore()
    # Center and 50-mile radius the regional graph was pulled with
    store.add_permanent(MADISON_ID, "Madison, WI", 43.0731, -89.4012, 80467, G_multi, G)
    state["regions"] = store
    print(f"Graph ready: {len(G.nodes)} nodes")
    yield
    state.clear()


# The frontend is served from this same app (mounted at the bottom of this
# file), so the page calls the API same-origin and needs no CORS.
app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    madison = state["regions"].get(MADISON_ID)
    return {"status": "ok", "nodes": len(madison.G.nodes)}


@app.get("/journeys")
def journeys():
    return JOURNEYS


@app.get("/geocode")
def geocode(q: str):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Enter a city to search for")
    try:
        return geocode_us(q)
    except Exception:
        raise HTTPException(status_code=502, detail="City search is unavailable right now. Try again in a moment.")


class RegionRequest(BaseModel):
    lat: float
    lon: float
    name: str


@app.post("/regions")
def create_region(req: RegionRequest):
    """Get a map region ready for a city. Poll GET /regions/{id} until status is ready."""
    return state["regions"].ensure_region(req.lat, req.lon, req.name).info()


@app.get("/regions/{region_id}")
def region_status(region_id: str):
    region = state["regions"].get(region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Unknown region")
    return region.info()


class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    # Leave both out for a loop that starts and ends at the start point
    end_lat: float | None = None
    end_lon: float | None = None
    target_distance_m: float
    # Optional: place this journey's stops along the route as landmarks
    journey_id: str | None = None
    region_id: str = MADISON_ID


@app.post("/route")
def route(req: RouteRequest):
    try:
        region = state["regions"].get_for_route(req.region_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown region. Pick your city again.")
    except RegionNotReady as e:
        raise HTTPException(status_code=409, detail=f"That city's map isn't ready: {e}")
    G, G_multi = region.G, region.G_multi

    points = [(req.start_lat, req.start_lon)]
    if req.end_lat is not None and req.end_lon is not None:
        points.append((req.end_lat, req.end_lon))
    if not all(region.contains(lat, lon) for lat, lon in points):
        raise HTTPException(status_code=400, detail=f"Pick points inside the {region.name} map area.")
    if region.max_target_m and req.target_distance_m > region.max_target_m:
        raise HTTPException(
            status_code=400,
            detail=f"Walks in {region.name} can be up to {region.max_target_m / 1000:.0f}km.",
        )

    journey = None
    if req.journey_id is not None:
        journey = JOURNEYS_BY_ID.get(req.journey_id)
        if journey is None:
            raise HTTPException(status_code=400, detail=f"Unknown journey: {req.journey_id}")

    start_node = ox.distance.nearest_nodes(G_multi, req.start_lon, req.start_lat)
    if (req.end_lat is None) != (req.end_lon is None):
        raise HTTPException(status_code=400, detail="Give both end_lat and end_lon, or neither for a loop")
    if req.end_lat is None:
        end_node = start_node
    else:
        # Two clicks that snap to the same node also become a loop
        end_node = ox.distance.nearest_nodes(G_multi, req.end_lon, req.end_lat)

    loop = start_node == end_node
    try:
        path, length, steps = find_path_with_restarts(
            G, start_node, end_node, req.target_distance_m,
            **(LOOP_SEARCH if loop else POINT_TO_POINT_SEARCH),
        )
    except UnreachableError as e:
        if e.shortest_m is None:
            raise HTTPException(status_code=404, detail="No walkable route connects these two points")
        raise HTTPException(
            status_code=422,
            detail=f"The shortest route between these points is {e.shortest_m:.0f}m. Raise the target to at least that.",
        )

    if path is None:
        raise HTTPException(status_code=422, detail="No route found near that target distance")

    coords = [[G.nodes[n]["y"], G.nodes[n]["x"]] for n in path]

    breakdown = highway_breakdown(G, path)
    trail_m = sum(l for h, l in breakdown if h in TRAIL_TYPES)

    # Group consecutive edges into trail/road runs so the map can color them
    segments = []
    for i, (u, v) in enumerate(zip(path[:-1], path[1:])):
        is_trail = G[u][v]["highway"] in TRAIL_TYPES
        if segments and segments[-1]["trail"] == is_trail:
            segments[-1]["path"].append(coords[i + 1])
        else:
            segments.append({"trail": is_trail, "path": [coords[i], coords[i + 1]]})

    landmarks = []
    if journey is not None:
        stops = journey["stops"]
        points = points_along_path(G, path, [s["at"] for s in stops])
        landmarks = [
            {"name": s["name"], "lat": p["lat"], "lon": p["lon"], "at_m": round(p["at_m"], 1)}
            for s, p in zip(stops, points)
        ]

    return {
        "loop": loop,
        "distance_m": round(length, 1),
        "target_m": req.target_distance_m,
        # False means no route hit the target, and this is the closest one found
        "within_tolerance": within_tolerance(length, req.target_distance_m),
        "num_nodes": len(path),
        "steps": steps,
        "path": coords,
        "trail_m": round(trail_m, 1),
        "trail_pct": round(trail_m / length * 100, 1),
        "breakdown": [{"highway": h, "meters": round(l, 1)} for h, l in breakdown],
        "segments": segments,
        "landmarks": landmarks,
    }


# Last, so the API routes above take precedence over static files
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")