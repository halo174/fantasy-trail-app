import networkx as nx
import pytest

from graph_utils import points_along_path, path_length
from journeys import JOURNEYS, JOURNEYS_BY_ID


# --- Journey data ---

def test_journey_ids_unique():
    assert len(JOURNEYS_BY_ID) == len(JOURNEYS)


@pytest.mark.parametrize("journey", JOURNEYS, ids=lambda j: j["id"])
def test_journey_stops_are_well_formed(journey):
    for key in ["id", "title", "source", "blurb", "suggested_km", "loop", "stops"]:
        assert key in journey
    ats = [s["at"] for s in journey["stops"]]
    assert len(ats) >= 2
    assert ats[0] == 0 and ats[-1] == 1
    assert ats == sorted(ats), "stops out of order"
    assert all(s["name"] for s in journey["stops"])


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
