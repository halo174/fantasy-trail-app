from contextlib import asynccontextmanager
from fastapi import FastAPI
import osmnx as ox
from fastapi import HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from pathfinding import find_path_with_restarts, within_tolerance, UnreachableError

from graph_utils import to_simple_graph, highway_breakdown, get_bridges, TRAIL_TYPES

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
    state["G_multi"] = G_multi
    state["G"] = to_simple_graph(G_multi)
    print("Finding bridges for loop routing...")
    get_bridges(state["G"])  # ~6s, cached on the graph so loop requests don't pay it
    print(f"Graph ready: {len(state['G'].nodes)} nodes")
    yield
    state.clear()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "nodes": len(state["G"].nodes)}

class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    # Leave both out for a loop that starts and ends at the start point
    end_lat: float | None = None
    end_lon: float | None = None
    target_distance_m: float


@app.post("/route")
def route(req: RouteRequest):
    G = state["G"]
    G_multi = state["G_multi"]

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
    }