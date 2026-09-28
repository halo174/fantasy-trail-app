from contextlib import asynccontextmanager
from fastapi import FastAPI
import osmnx as ox
from fastapi import HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from pathfinding import find_path_with_restarts

from graph_utils import to_simple_graph

state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading graph...")
    G_multi = ox.load_graphml("madison_50mi_tiled_walk_network.graphml")
    state["G_multi"] = G_multi
    state["G"] = to_simple_graph(G_multi)
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
    end_lat: float
    end_lon: float
    target_distance_m: float


@app.post("/route")
def route(req: RouteRequest):
    G = state["G"]
    G_multi = state["G_multi"]

    start_node = ox.distance.nearest_nodes(G_multi, req.start_lon, req.start_lat)
    end_node = ox.distance.nearest_nodes(G_multi, req.end_lon, req.end_lat)

    if start_node == end_node:
        raise HTTPException(status_code=400, detail="Start and end snap to the same node")

    try:
        path, length, steps = find_path_with_restarts(
            G, start_node, end_node, req.target_distance_m, max_restarts=3
        )
    except ValueError:
        raise HTTPException(status_code=404, detail="End point is not reachable from start point")

    if path is None:
        raise HTTPException(status_code=422, detail="No route found near that target distance")

    coords = [[G.nodes[n]["y"], G.nodes[n]["x"]] for n in path]

    return {
        "distance_m": round(length, 1),
        "num_nodes": len(path),
        "steps": steps,
        "path": coords,
    }