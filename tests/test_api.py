"""
API tests on a small fake map, so they don't load the regional GraphML.
TestClient is used without `with`, which skips the startup graph load.
"""
import random

import networkx as nx
import pytest
from fastapi.testclient import TestClient

import api
from journeys import JOURNEYS_BY_ID

# 0.0009 deg of latitude is about 100m, so this is roughly a 100m street grid
STEP = 0.0009
LAT0, LON0 = 43.0, -89.4
N = 10


def node_id(i, j):
    # Integer IDs like real OSM nodes; osmnx's nearest_nodes can't index tuples
    return i * N + j


def grid_map():
    G = nx.MultiDiGraph(crs="epsg:4326")
    for i in range(N):
        for j in range(N):
            G.add_node(node_id(i, j), x=LON0 + i * STEP, y=LAT0 + j * STEP)
    for i in range(N):
        for j in range(N):
            for di, dj in [(1, 0), (0, 1)]:
                if i + di < N and j + dj < N:
                    a, b = node_id(i, j), node_id(i + di, j + dj)
                    G.add_edge(a, b, length=100.0, highway="footway")
                    G.add_edge(b, a, length=100.0, highway="footway")
    return G


@pytest.fixture
def client(monkeypatch):
    random.seed(7)
    G_multi = grid_map()
    monkeypatch.setitem(api.state, "G_multi", G_multi)
    monkeypatch.setitem(api.state, "G", api.to_simple_graph(G_multi))
    return TestClient(api.app)


def corner(i, j):
    return {"lat": LAT0 + j * STEP, "lon": LON0 + i * STEP}


def test_journeys_endpoint(client):
    r = client.get("/journeys")
    assert r.status_code == 200
    ids = [j["id"] for j in r.json()]
    assert "oz" in ids and len(ids) == len(JOURNEYS_BY_ID)


def test_route_with_journey_places_landmarks(client):
    s, e = corner(0, 0), corner(5, 5)
    r = client.post("/route", json={
        "start_lat": s["lat"], "start_lon": s["lon"],
        "end_lat": e["lat"], "end_lon": e["lon"],
        "target_distance_m": 1400,
        "journey_id": "odyssey",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    stops = JOURNEYS_BY_ID["odyssey"]["stops"]
    landmarks = data["landmarks"]
    assert [lm["name"] for lm in landmarks] == [st["name"] for st in stops]
    assert landmarks[0]["at_m"] == 0
    assert landmarks[-1]["at_m"] == pytest.approx(data["distance_m"], abs=0.2)
    # First and last landmarks sit on the route's ends
    assert [landmarks[0]["lat"], landmarks[0]["lon"]] == pytest.approx(data["path"][0])
    assert [landmarks[-1]["lat"], landmarks[-1]["lon"]] == pytest.approx(data["path"][-1])


def test_loop_with_journey(client):
    s = corner(4, 4)
    r = client.post("/route", json={
        "start_lat": s["lat"], "start_lon": s["lon"],
        "target_distance_m": 2000, "journey_id": "oz",
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["loop"]
    assert len(data["landmarks"]) == len(JOURNEYS_BY_ID["oz"]["stops"])


def test_route_without_journey_has_no_landmarks(client):
    s = corner(4, 4)
    r = client.post("/route", json={"start_lat": s["lat"], "start_lon": s["lon"], "target_distance_m": 1200})
    assert r.status_code == 200
    assert r.json()["landmarks"] == []


def test_unknown_journey_is_400(client):
    s = corner(4, 4)
    r = client.post("/route", json={
        "start_lat": s["lat"], "start_lon": s["lon"],
        "target_distance_m": 1200, "journey_id": "narnia",
    })
    assert r.status_code == 400
    assert "narnia" in r.json()["detail"]


def test_frontend_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Fantasy Trail" in r.text
    assert client.get("/app.js").status_code == 200
