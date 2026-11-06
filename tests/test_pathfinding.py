"""
Fast tests on small synthetic graphs, no GraphML needed.
Run with: venv/bin/python -m pytest
"""
import random

import networkx as nx
import pytest

import pathfinding
from graph_utils import path_length, highway_breakdown, TRAIL_TYPES
from pathfinding import (
    find_path_with_restarts,
    within_tolerance,
    UnreachableError,
)


def add_way(G, u, v, length, highway="residential"):
    """Two-way edge, matching the shape to_simple_graph produces."""
    G.add_edge(u, v, length=length, highway=highway)
    G.add_edge(v, u, length=length, highway=highway)


def grid_graph(n=8, spacing=100.0):
    """n x n grid of 100m blocks. Shortest corner-to-corner is 2*(n-1)*spacing."""
    G = nx.DiGraph()
    for x in range(n):
        for y in range(n):
            G.add_node((x, y), x=x, y=y)
            if x + 1 < n:
                add_way(G, (x, y), (x + 1, y), spacing)
            if y + 1 < n:
                add_way(G, (x, y), (x, y + 1), spacing)
    return G


@pytest.fixture(autouse=True)
def seeded():
    random.seed(1234)


@pytest.mark.parametrize("multiplier", [1.0, 1.5, 2.5])
def test_route_is_valid_and_within_tolerance(multiplier):
    G = grid_graph()
    start, end = (0, 0), (7, 7)
    target = 1400 * multiplier

    path, length, steps = find_path_with_restarts(G, start, end, target)

    assert path[0] == start and path[-1] == end
    assert len(path) == len(set(path)), "route revisits a node"
    assert all(G.has_edge(u, v) for u, v in zip(path[:-1], path[1:]))
    assert length == pytest.approx(path_length(G, path))
    assert within_tolerance(length, target)


def test_target_below_shortest_reports_shortest():
    G = grid_graph()
    with pytest.raises(UnreachableError) as exc:
        find_path_with_restarts(G, (0, 0), (7, 7), 500)
    assert exc.value.shortest_m == pytest.approx(1400)


def test_disconnected_points_report_no_route():
    G = grid_graph()
    G.add_node("island", x=99, y=99)
    with pytest.raises(UnreachableError) as exc:
        find_path_with_restarts(G, (0, 0), "island", 2000)
    assert exc.value.shortest_m is None


def test_prefers_trail_over_equal_length_road():
    # Two equal 1000m routes from A to B, one trail and one road
    G = nx.DiGraph()
    for n in ["A", "B", "t", "r"]:
        G.add_node(n, x=0, y=0)
    add_way(G, "A", "t", 500, "path")
    add_way(G, "t", "B", 500, "path")
    add_way(G, "A", "r", 500, "residential")
    add_way(G, "r", "B", 500, "residential")

    trail_wins = 0
    for _ in range(100):
        path, _, _ = find_path_with_restarts(G, "A", "B", 1000)
        trail_m = sum(l for h, l in highway_breakdown(G, path) if h in TRAIL_TYPES)
        trail_wins += trail_m == 1000
    # ROAD_PENALTY = 15 means the trail should win about 15 out of 16 times
    assert trail_wins >= 85


def test_restarts_keep_going_after_out_of_tolerance_attempt(monkeypatch):
    # First attempt finds a route that's way off, second one hits the target.
    # The wrapper has to keep retrying instead of returning the first route.
    G = grid_graph()
    results = iter([
        (["far"], 1500.0, 10),
        (["good"], 2000.0, 10),
    ])
    monkeypatch.setattr(pathfinding, "find_path_matching_distance_dfs", lambda *a, **k: next(results))

    path, length, steps = find_path_with_restarts(G, (0, 0), (7, 7), 2000, max_restarts=5)
    assert path == ["good"]
    assert steps == 20


def test_restarts_return_closest_when_none_within_tolerance(monkeypatch):
    G = grid_graph()
    results = iter([
        (["worse"], 1400.0, 10),
        (None, None, 10),
        (["closer"], 1550.0, 10),
    ])
    monkeypatch.setattr(pathfinding, "find_path_matching_distance_dfs", lambda *a, **k: next(results))

    path, length, steps = find_path_with_restarts(G, (0, 0), (7, 7), 2000, max_restarts=3)
    assert path == ["closer"]
    assert not within_tolerance(length, 2000)
    assert steps == 30


# --- Loops (start == end) ---

def undirected_edges(path):
    return [frozenset(e) for e in zip(path[:-1], path[1:])]


@pytest.mark.parametrize("target", [800, 2000, 4000])
def test_loop_is_valid_and_within_tolerance(target):
    G = grid_graph()
    start = (3, 3)

    path, length, _ = find_path_with_restarts(G, start, start, target)

    assert path[0] == start and path[-1] == start
    assert len(path) > 2
    edges = undirected_edges(path)
    assert len(edges) == len(set(edges)), "loop retraces a segment"
    assert all(G.has_edge(u, v) for u, v in zip(path[:-1], path[1:]))
    assert length == pytest.approx(path_length(G, path))
    assert within_tolerance(length, target)


def test_loop_can_cross_its_own_junction():
    # Figure-8: two 300m triangles that only share node J. Hitting 600m
    # from S means passing through J twice, which a simple path can't do.
    G = nx.DiGraph()
    for n in ["S", "a", "J", "b", "c"]:
        G.add_node(n, x=0, y=0)
    for u, v in [("S", "a"), ("a", "J"), ("J", "S"), ("J", "b"), ("b", "c"), ("c", "J")]:
        add_way(G, u, v, 100)

    path, length, _ = find_path_with_restarts(G, "S", "S", 600, tolerance=0.05)
    assert length == pytest.approx(600)
    assert path.count("J") == 2


def test_no_loop_on_dead_end_trail():
    # A straight trail has no loop without retracing it
    G = nx.DiGraph()
    for i in range(5):
        G.add_node(i, x=i, y=0)
    for i in range(4):
        add_way(G, i, i + 1, 100, "path")

    path, length, _ = find_path_with_restarts(G, 0, 0, 800, max_restarts=2)
    assert path is None


def test_loop_from_dead_end_stub():
    # Start at the tip of a 150m stub hanging off the grid. The only way out
    # is the stub, so the loop walks it out and back and loops from the junction.
    G = grid_graph()
    G.add_node("s1", x=-1, y=0)
    G.add_node("tip", x=-2, y=0)
    add_way(G, (0, 0), "s1", 100)
    add_way(G, "s1", "tip", 50)

    path, length, _ = find_path_with_restarts(G, "tip", "tip", 1500)

    assert path[:3] == ["tip", "s1", (0, 0)]
    assert path[-3:] == [(0, 0), "s1", "tip"]
    assert length == pytest.approx(path_length(G, path))
    assert within_tolerance(length, 1500)
    # Only the stub is repeated
    inner = undirected_edges(path[2:-2])
    assert len(inner) == len(set(inner))


def test_loop_target_shorter_than_stub():
    G = grid_graph()
    G.add_node("tip", x=-1, y=0)
    add_way(G, (0, 0), "tip", 500)
    path, _, _ = find_path_with_restarts(G, "tip", "tip", 800)
    assert path is None


def test_loop_from_branching_stub_tree():
    # Like the real urban start that failed: the start's stub meets a node that
    # looks like a junction but its other branch is another dead end. The loop
    # has to walk out to the grid and never wander into the side stub.
    G = grid_graph()
    for n in ["tip", "fork", "side", "side2"]:
        G.add_node(n, x=-1, y=0)
    add_way(G, "tip", "fork", 50)
    add_way(G, "fork", "side", 50)
    add_way(G, "side", "side2", 50)
    add_way(G, "fork", (0, 0), 100)

    for _ in range(20):
        path, length, _ = find_path_with_restarts(G, "tip", "tip", 2000)
        assert path[:3] == ["tip", "fork", (0, 0)]
        assert path[-3:] == [(0, 0), "fork", "tip"]
        assert "side" not in path
        assert within_tolerance(length, 2000)
