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
