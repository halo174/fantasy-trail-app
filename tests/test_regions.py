"""RegionStore tests. Pulls are faked, so no network is used."""
import networkx as nx
import pytest

from regions import RegionStore, RegionNotReady, READY, FAILED, STORED, PULL_RADIUS_M

MADISON = (43.0731, -89.4012)
ANN_ARBOR = (42.2808, -83.7430)
BOSTON = (42.3601, -71.0589)


def small_map(lat, lon):
    """A 3x3 grid of 100m blocks around (lat, lon), shaped like an osmnx graph."""
    G = nx.MultiDiGraph(crs="epsg:4326")
    step = 0.0009
    for i in range(3):
        for j in range(3):
            G.add_node(i * 3 + j, x=lon + i * step, y=lat + j * step)
    for i in range(3):
        for j in range(3):
            for di, dj in [(1, 0), (0, 1)]:
                if i + di < 3 and j + dj < 3:
                    a, b = i * 3 + j, (i + di) * 3 + (j + dj)
                    G.add_edge(a, b, length=100.0, highway="residential")
                    G.add_edge(b, a, length=100.0, highway="residential")
    return G


class FakePull:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __call__(self, lat, lon, radius_m):
        self.calls.append((lat, lon, radius_m))
        if self.fail:
            raise TimeoutError("Overpass timed out")
        return small_map(lat, lon)


def make_store(tmp_path, pull, **kw):
    store = RegionStore(pull_fn=pull, region_dir=tmp_path, background=False, **kw)
    G = small_map(*MADISON)
    store.add_permanent("madison", "Madison, WI", *MADISON, 80467, G, nx.DiGraph(G))
    return store


def test_city_inside_madison_reuses_it(tmp_path):
    pull = FakePull()
    store = make_store(tmp_path, pull)
    region = store.ensure_region(43.0961, -89.5113, "Middleton, WI")
    assert region.id == "madison"
    assert pull.calls == []


def test_new_city_is_pulled_once_and_cached(tmp_path):
    pull = FakePull()
    store = make_store(tmp_path, pull)
    region = store.ensure_region(*ANN_ARBOR, "Ann Arbor, MI")
    assert region.status == READY
    assert pull.calls == [(*ANN_ARBOR, PULL_RADIUS_M)]
    assert (tmp_path / f"{region.id}.graphml").exists()
    assert region.max_target_m is not None

    again = store.ensure_region(*ANN_ARBOR, "Ann Arbor, MI")
    assert again is region
    assert len(pull.calls) == 1


def test_cached_city_loads_from_disk_after_restart(tmp_path):
    make_store(tmp_path, FakePull()).ensure_region(*ANN_ARBOR, "Ann Arbor, MI")

    pull = FakePull()
    region = make_store(tmp_path, pull).ensure_region(*ANN_ARBOR, "Ann Arbor, MI")
    assert region.status == READY
    assert pull.calls == []
    assert len(region.G.nodes) == 9


def test_failed_pull_reports_error_and_can_retry(tmp_path):
    store = make_store(tmp_path, FakePull(fail=True))
    region = store.ensure_region(*ANN_ARBOR, "Ann Arbor, MI")
    assert region.status == FAILED
    assert "Ann Arbor" in region.error and "timed out" in region.error
    with pytest.raises(RegionNotReady):
        store.get_for_route(region.id)

    store.pull_fn = FakePull()
    retried = store.ensure_region(*ANN_ARBOR, "Ann Arbor, MI")
    assert retried.status == READY


def test_least_recently_used_city_is_evicted_and_reloads(tmp_path):
    pull = FakePull()
    store = make_store(tmp_path, pull, max_loaded=1)
    ann_arbor = store.ensure_region(*ANN_ARBOR, "Ann Arbor, MI")
    boston = store.ensure_region(*BOSTON, "Boston, MA")

    assert boston.status == READY
    assert ann_arbor.status == STORED and ann_arbor.G is None
    assert ann_arbor.info()["status"] == "ready"  # still usable from the client's view
    assert store.get("madison").status == READY  # permanent, never evicted

    reloaded = store.get_for_route(ann_arbor.id)
    assert reloaded.status == READY and reloaded.G is not None
    assert len(pull.calls) == 2  # reloaded from disk, not pulled again
    assert boston.status == STORED
