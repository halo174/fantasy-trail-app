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
from regions import RegionStore, Region, PREPARING, FAILED
from features import FeatureStore
from shapely.geometry import LineString

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
def store(monkeypatch, tmp_path):
    random.seed(7)
    G_multi = grid_map()
    store = RegionStore(pull_fn=fail_pull, region_dir=tmp_path, background=False)
    # Madison's real radius, so nearby cities count as covered like in the app
    store.add_permanent(api.MADISON_ID, "Testville", LAT0 + 4.5 * STEP, LON0 + 4.5 * STEP, 80467,
                        G_multi, api.to_simple_graph(G_multi))
    monkeypatch.setitem(api.state, "regions", store)
    return store


def river(lat, lon, radius_m):
    """Fake feature download: a named river along the grid's row j=8."""
    return [{"terrain": "water", "name": "The Bruinen",
             "geometry": LineString([(LON0, LAT0 + 8 * STEP), (LON0 + 9 * STEP, LAT0 + 8 * STEP)])}]


def no_features(lat, lon, radius_m):
    raise TimeoutError("Overpass timed out")


@pytest.fixture
def features(monkeypatch, tmp_path):
    fs = FeatureStore(fetch_fn=river, feature_dir=tmp_path / "features", background=False)
    monkeypatch.setitem(api.state, "features", fs)
    return fs


@pytest.fixture
def client(store, features):
    return TestClient(api.app)


def fail_pull(lat, lon, radius_m):
    raise AssertionError("tests must not pull from OSM")


def corner(i, j):
    return {"lat": LAT0 + j * STEP, "lon": LON0 + i * STEP}


def walk(client, progress_km, target_m=2000, journey_id="frodo", at=(4, 4)):
    s = corner(*at)
    return client.post("/route", json={
        "start_lat": s["lat"], "start_lon": s["lon"], "target_distance_m": target_m,
        "journey_id": journey_id, "progress_km": progress_km,
    })


def test_journeys_endpoint(client):
    r = client.get("/journeys")
    assert r.status_code == 200
    assert [j["id"] for j in r.json()] == list(JOURNEYS_BY_ID)


def test_walk_reaching_a_stop_lands_it_on_matching_terrain(client):
    # Rivendell (water) is at 735km; starting at 734.2km it's due 800m in
    r = walk(client, progress_km=734.2)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["features_ready"]
    (lm,) = data["landmarks"]
    assert lm["name"] == "Rivendell" and lm["journey_km"] == 735
    assert lm["landed_on"] == "water" and lm["place_name"] == "The Bruinen"
    assert lm["lat"] == pytest.approx(LAT0 + 8 * STEP)  # on the river row
    assert 0 < lm["at_m"] < data["distance_m"]

    j = data["journey"]
    assert j["credit_km"] >= 0.8  # at least up to Rivendell
    assert j["next_stop"]["name"] == "The gates of Moria"
    assert j["next_stop"]["km_away"] == pytest.approx(1285 - j["progress_after_km"], abs=0.1)
    assert not j["finished"]


def test_walk_between_stops_has_no_landmarks(client):
    data = walk(client, progress_km=100).json()
    assert data["landmarks"] == []
    assert data["journey"]["next_stop"]["name"] == "Bucklebury Ferry"


def test_stop_falls_back_to_proportional_spot_without_features(client, monkeypatch, tmp_path):
    monkeypatch.setitem(api.state, "features", FeatureStore(fetch_fn=no_features, feature_dir=tmp_path / "f2", background=False))
    data = walk(client, progress_km=734.2).json()
    assert not data["features_ready"]
    (lm,) = data["landmarks"]
    assert lm["landed_on"] is None
    assert lm["at_m"] == pytest.approx(800, abs=1)


def test_last_walk_is_capped_at_the_journey_end(client):
    data = walk(client, progress_km=2864, target_m=5000).json()
    assert data["target_m"] == pytest.approx(1000)
    (lm,) = data["landmarks"]
    assert lm["name"] == "Mount Doom"
    assert data["journey"]["finished"]
    assert data["journey"]["next_stop"] is None


def test_finished_journey_is_400(client):
    r = walk(client, progress_km=2865)
    assert r.status_code == 400
    assert "finished" in r.json()["detail"]


def test_prepare_features_endpoint(client):
    s = corner(4, 4)
    info = client.post("/features", json={"lat": s["lat"], "lon": s["lon"]}).json()
    assert info["status"] == "ready"
    assert client.get(f"/features/{info['id']}").json()["status"] == "ready"
    assert client.get("/features/nope").status_code == 404


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


# --- Regions ---

def test_route_in_region_not_ready_is_409(client, store):
    r = Region("busy", "Busytown", LAT0, LON0, 2000)
    r.status = PREPARING
    store.regions["busy"] = r
    s = corner(4, 4)
    resp = client.post("/route", json={
        "start_lat": s["lat"], "start_lon": s["lon"], "target_distance_m": 1200, "region_id": "busy",
    })
    assert resp.status_code == 409


def test_route_in_unknown_region_is_404(client):
    s = corner(4, 4)
    resp = client.post("/route", json={
        "start_lat": s["lat"], "start_lon": s["lon"], "target_distance_m": 1200, "region_id": "atlantis",
    })
    assert resp.status_code == 404


def test_point_outside_region_is_400(client):
    resp = client.post("/route", json={"start_lat": 44.0, "start_lon": -89.4, "target_distance_m": 1200})
    assert resp.status_code == 400
    assert "Testville" in resp.json()["detail"]


def test_target_over_region_cap_is_400(client, store):
    store.get(api.MADISON_ID).max_target_m = 1000
    s = corner(4, 4)
    resp = client.post("/route", json={"start_lat": s["lat"], "start_lon": s["lon"], "target_distance_m": 1200})
    assert resp.status_code == 400
    assert "up to 1km" in resp.json()["detail"]


def test_region_endpoints(client):
    # A point inside the permanent region reuses it
    resp = client.post("/regions", json={"lat": LAT0 + 4.5 * STEP, "lon": LON0 + 4.5 * STEP, "name": "Nearby"})
    assert resp.status_code == 200
    assert resp.json()["id"] == api.MADISON_ID
    assert client.get(f"/regions/{api.MADISON_ID}").json()["status"] == "ready"
    assert client.get("/regions/nope").status_code == 404


def test_geocode_endpoint(client, monkeypatch):
    monkeypatch.setattr(api, "geocode_us", lambda q: [{"name": "Ann Arbor, Michigan", "lat": 42.28, "lon": -83.74}])
    resp = client.get("/geocode", params={"q": "ann arbor"})
    assert resp.json()[0]["name"] == "Ann Arbor, Michigan"


def test_geocode_failure_is_502(client, monkeypatch):
    def boom(q):
        raise ConnectionError("down")
    monkeypatch.setattr(api, "geocode_us", boom)
    assert client.get("/geocode", params={"q": "x"}).status_code == 502


def test_short_via_route_falls_back_to_plain_walk(client, monkeypatch):
    # If bending through matching places can't fit the distance, the user
    # gets a walk of the length they asked for, with the stop placed plainly
    def short_via(G, start, end, target, stops, anchors, tolerance=0.2):
        return [start], target * 0.5, 0, [{"node": start, "at_m": 0, "terrain": "water", "place_name": "x"}]
    monkeypatch.setattr(api, "find_route_via", short_via)
    data = walk(client, progress_km=734.2).json()
    assert data["within_tolerance"]
    assert data["landmarks"][0]["landed_on"] is None
