import networkx as nx
import pytest

from graph_utils import points_along_path, path_length
from journeys import JOURNEYS, JOURNEYS_BY_ID, stops_due, next_stop
from features import TERRAINS


# --- Journey data ---

def test_journey_ids_unique():
    assert len(JOURNEYS_BY_ID) == len(JOURNEYS)


@pytest.mark.parametrize("journey", JOURNEYS, ids=lambda j: j["id"])
def test_journey_stops_are_well_formed(journey):
    for key in ["id", "title", "source", "blurb", "total_km", "distance_note", "stops"]:
        assert key in journey
    kms = [s["km"] for s in journey["stops"]]
    assert kms[0] == 0
    assert kms[-1] == journey["total_km"]
    assert kms == sorted(kms) and len(set(kms)) == len(kms), "stops out of order or duplicated"
    for s in journey["stops"]:
        assert s["name"]
        assert s["terrain"] in TERRAINS


def test_frodo_stage_totals_match_fonstad():
    # Rivendell at 735km and Mount Doom at 2,865km, per Fonstad's Atlas
    stops = {s["name"]: s["km"] for s in JOURNEYS_BY_ID["frodo"]["stops"]}
    assert stops["Rivendell"] == 735
    assert stops["Mount Doom"] == 2865


# --- Which stops a walk reaches ---

def test_stops_due_on_a_walk():
    frodo = JOURNEYS_BY_ID["frodo"]
    assert [s["name"] for s in stops_due(frodo, 730, 10)] == ["Rivendell"]
    assert stops_due(frodo, 0, 5) == []  # the start stop never counts as reached
    assert [s["name"] for s in stops_due(frodo, 2670, 10)] == ["Cirith Ungol"]
    assert [s["name"] for s in stops_due(frodo, 2630, 50)] == ["Minas Morgul", "Cirith Ungol"]


def test_stop_exactly_at_walk_end_is_due():
    frodo = JOURNEYS_BY_ID["frodo"]
    assert [s["name"] for s in stops_due(frodo, 730, 5)] == ["Rivendell"]


def test_next_stop():
    frodo = JOURNEYS_BY_ID["frodo"]
    assert next_stop(frodo, 0)["name"] == "Bucklebury Ferry"
    assert next_stop(frodo, 735)["name"] == "The gates of Moria"
    assert next_stop(frodo, 2865) is None


# --- points_along_path ---

def straight_line():
    """A -> B -> C along a line of longitude: 100m then 300m, 0.001 deg lat per node step."""
    G = nx.DiGraph()
    G.add_node("A", x=-89.4, y=43.000)
    G.add_node("B", x=-89.4, y=43.001)
    G.add_node("C", x=-89.4, y=43.004)
    G.add_edge("A", "B", length=100.0)
    G.add_edge("B", "C", length=300.0)
    return G


def test_points_at_ends_are_the_end_nodes():
    G = straight_line()
    start, end = points_along_path(G, ["A", "B", "C"], [0.0, 1.0])
    assert (start["lat"], start["lon"], start["at_m"]) == (43.000, -89.4, 0)
    assert end["lat"] == pytest.approx(43.004)
    assert end["at_m"] == pytest.approx(400)


def test_points_interpolate_inside_edges():
    G = straight_line()
    path = ["A", "B", "C"]
    # 0.125 -> 50m, halfway along A-B. 0.625 -> 250m, halfway along B-C.
    first, second = points_along_path(G, path, [0.125, 0.625])
    assert first["lat"] == pytest.approx(43.0005)
    assert second["lat"] == pytest.approx(43.0025)
    assert second["at_m"] == pytest.approx(0.625 * path_length(G, path))


def test_point_exactly_on_a_node():
    G = straight_line()
    (p,) = points_along_path(G, ["A", "B", "C"], [0.25])
    assert p["lat"] == pytest.approx(43.001)
