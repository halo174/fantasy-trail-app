"""
Terrain anchors and routing through journey stops, on a synthetic map.
No network: OSM feature downloads are faked.
"""
import random

import networkx as nx
import pytest
from shapely.geometry import Polygon, LineString, Point

from features import (
    TERRAINS, FeatureStore, find_anchors, terrain_order, classify, nodes_within, READY, FAILED,
)
from graph_utils import path_length, to_simple_graph
from pathfinding import find_route_via, within_tolerance

N = 10
LAT0, LON0 = 43.0, -89.4
DLAT = 100 / 110540                          # 100m north
DLON = 100 / (111320 * 0.7313537)            # 100m east at 43N (cos 43deg)


def nid(i, j):
    return i * N + j


def lonlat(i, j):
    return LON0 + i * DLON, LAT0 + j * DLAT


def grid(bridge_edge=None):
    """N x N grid of 100m blocks. i is east, j is north."""
    G = nx.DiGraph()
    for i in range(N):
        for j in range(N):
            x, y = lonlat(i, j)
            G.add_node(nid(i, j), x=x, y=y)
    for i in range(N):
        for j in range(N):
            for di, dj in [(1, 0), (0, 1)]:
                if i + di < N and j + dj < N:
                    a, b = nid(i, j), nid(i + di, j + dj)
                    is_bridge = bridge_edge == {a, b}
                    for u, v in [(a, b), (b, a)]:
                        G.add_edge(u, v, length=100.0, highway="footway",
                                   bridge=is_bridge, tunnel=False, name="Troll Bridge" if is_bridge else None)
    return G


def block(i0, j0, i1, j1):
    """Polygon (lon/lat) covering grid cells from (i0, j0) to (i1, j1), inset 10m."""
    pad_x, pad_y = 0.1 * DLON, 0.1 * DLAT
    (x0, y0), (x1, y1) = lonlat(i0, j0), lonlat(i1, j1)
    return Polygon([(x0 + pad_x, y0 + pad_y), (x1 - pad_x, y0 + pad_y), (x1 - pad_x, y1 - pad_y), (x0 + pad_x, y1 - pad_y)])


@pytest.fixture(autouse=True)
def seeded():
    random.seed(42)


# --- Terrain config ---

def test_terrain_fallbacks_are_known_terrains():
    for terrain, spec in TERRAINS.items():
        assert all(f in TERRAINS for f in spec["fallback"]), terrain
        order = terrain_order(terrain)
        assert order[0] == terrain and len(order) == len(set(order))


def test_classify_rows():
    assert classify({"natural": "wood"}) == ["forest"]
    assert classify({"waterway": "river"}) == ["water"]
    assert classify({"natural": "wetland"}) == ["marsh"]
    assert classify({"leisure": "playground"}) == []


# --- Anchors ---

def test_find_anchors_from_features_and_edges():
    G = grid(bridge_edge={nid(1, 1), nid(2, 1)})
    features = [
        {"terrain": "forest", "name": "Old Forest", "geometry": block(4, 4, 6, 6)},
        {"terrain": "water", "name": "The Brandywine", "geometry": LineString([lonlat(0, 8), lonlat(9, 8)])},
        {"terrain": "tower", "name": None, "geometry": Point(lonlat(8, 1))},
    ]
    anchors = find_anchors(G, features, G.nodes)

    # Nodes inside the woods block, plus its edge nodes within 30m (10m inset)
    assert set(anchors["forest"]) == {nid(i, j) for i in range(4, 7) for j in range(4, 7)}
    assert anchors["forest"][nid(5, 5)] == "Old Forest"
    assert set(anchors["water"]) == {nid(i, 8) for i in range(N)}
    assert set(anchors["tower"]) == {nid(8, 1)}
    assert set(anchors["bridge"]) == {nid(1, 1), nid(2, 1)}
    assert anchors["bridge"][nid(1, 1)] == "Troll Bridge"
    assert anchors["marsh"] == {}


def test_anchors_limited_to_near_nodes():
    G = grid()
    features = [{"terrain": "forest", "name": None, "geometry": block(0, 0, 9, 9)}]
    near = nodes_within(G, nid(0, 0), 150)  # (0,0), (1,0), (0,1)
    assert set(find_anchors(G, features, near)["forest"]) == {nid(0, 0), nid(1, 0), nid(0, 1)}


def test_bridge_and_tunnel_tags_survive_simple_graph():
    M = nx.MultiDiGraph()
    M.add_node(1, x=0, y=0)
    M.add_node(2, x=0, y=0)
    M.add_node(3, x=0, y=0)
    M.add_edge(1, 2, length=50.0, highway="footway", bridge="boardwalk", name=["Lakeshore Path", "x"])
    M.add_edge(2, 3, length=50.0, highway="footway", tunnel="building_passage")
    M.add_edge(1, 3, length=50.0, highway="residential", bridge="no")
    G = to_simple_graph(M)
    assert G[1][2]["bridge"] and G[1][2]["name"] == "Lakeshore Path"
    assert G[2][3]["tunnel"] and not G[2][3]["bridge"]
    assert not G[1][3]["bridge"]


# --- Feature store ---

class FakeFetch:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail

    def __call__(self, lat, lon, radius_m):
        self.calls += 1
        if self.fail:
            raise TimeoutError("Overpass timed out")
        return [{"terrain": "forest", "name": "Woods", "geometry": Point(lon, lat)}]


def test_feature_store_downloads_once_and_caches_to_disk(tmp_path):
    fetch = FakeFetch()
    store = FeatureStore(fetch_fn=fetch, feature_dir=tmp_path, background=False)
    assert store.ready_features(43.07, -89.41)[0]["name"] == "Woods"
    assert store.ready_features(43.071, -89.412) is not None  # same ~5km cell
    assert fetch.calls == 1

    fetch2 = FakeFetch()
    again = FeatureStore(fetch_fn=fetch2, feature_dir=tmp_path, background=False)
    assert again.ready_features(43.07, -89.41) is not None
    assert fetch2.calls == 0  # loaded from disk


def test_feature_store_failure_is_reported_and_retried(tmp_path):
    store = FeatureStore(fetch_fn=FakeFetch(fail=True), feature_dir=tmp_path, background=False)
    cell = store.ensure(43.07, -89.40)
    assert cell.status == FAILED and "timed out" in cell.error
    store.fetch_fn = FakeFetch()
    assert store.ensure(43.07, -89.40).status == READY


# --- Routing through stops ---

def stop(name, terrain):
    return {"name": name, "terrain": terrain, "terrains": terrain_order(terrain)}


def forest_anchors(G):
    features = [{"terrain": "forest", "name": "Old Forest", "geometry": block(4, 4, 5, 5)}]
    return find_anchors(G, features, G.nodes)


def segments(path):
    return [frozenset(e) for e in zip(path[:-1], path[1:])]


@pytest.mark.parametrize("trial", range(5))
def test_loop_passes_through_forest_near_due_distance(trial):
    random.seed(trial)
    G = grid()
    anchors = forest_anchors(G)
    start = nid(1, 1)

    path, length, _, (placement,) = find_route_via(G, start, start, 2400, [(stop("Lothlórien", "forest"), 1000)], anchors)

    assert path[0] == start and path[-1] == start
    assert placement["node"] in anchors["forest"] and placement["node"] in path
    assert placement["terrain"] == "forest" and placement["place_name"] == "Old Forest"
    assert 750 <= placement["at_m"] <= 1250
    assert placement["at_m"] == pytest.approx(path_length(G, path[: path.index(placement["node"]) + 1]))
    segs = segments(path)
    assert len(segs) == len(set(segs)), "walk reuses a segment"
    assert length == pytest.approx(path_length(G, path))
    assert within_tolerance(length, 2400)


def test_point_to_point_with_two_stops_in_order():
    # Bridge placed so there's still slack to reach the end after it
    G = grid(bridge_edge={nid(7, 6), nid(8, 6)})
    anchors = forest_anchors(G)
    anchors.update({k: v for k, v in find_anchors(G, [], G.nodes).items() if v})
    start, end = nid(0, 0), nid(9, 9)

    path, length, _, placements = find_route_via(
        G, start, end, 2600,
        [(stop("Mirkwood", "forest"), 900), (stop("The bridge", "bridge"), 1800)],
        anchors,
    )
    forest, bridge = placements
    assert forest["terrain"] == "forest" and bridge["terrain"] == "bridge"
    assert path.index(forest["node"]) < path.index(bridge["node"])
    assert forest["at_m"] < bridge["at_m"]
    segs = segments(path)
    assert len(segs) == len(set(segs))
    assert within_tolerance(length, 2600)


def test_stop_uses_fallback_terrain():
    G = grid()
    anchors = forest_anchors(G)
    # A hill stop with no hills or towers falls back to forest
    _, _, _, (placement,) = find_route_via(G, nid(1, 1), nid(1, 1), 2400, [(stop("Weathertop", "hill"), 1000)], anchors)
    assert placement["terrain"] == "forest"


def test_no_matching_place_returns_none():
    G = grid()
    anchors = find_anchors(G, [], G.nodes)  # nothing but (absent) bridges and tunnels
    assert find_route_via(G, nid(1, 1), nid(1, 1), 2400, [(stop("Dead Marshes", "marsh"), 1000)], anchors) is None


def test_stop_due_at_walk_end_lands_at_end():
    G = grid()
    start, end = nid(0, 0), nid(5, 5)
    path, length, _, (placement,) = find_route_via(
        G, start, end, 1400, [(stop("Mount Doom", "hill"), 1400)], forest_anchors(G),
    )
    assert placement["node"] == end and placement["terrain"] is None
    assert placement["at_m"] == pytest.approx(length)


def test_loop_whose_only_stop_is_at_the_end():
    # The last walk of a journey: the final stop is due exactly where a loop ends
    G = grid()
    start = nid(3, 3)
    path, length, _, (placement,) = find_route_via(
        G, start, start, 1600, [(stop("Mount Doom", "hill"), 1600)], forest_anchors(G),
    )
    assert path[0] == start and path[-1] == start and len(path) > 2
    assert within_tolerance(length, 1600)
    assert placement["node"] == start
