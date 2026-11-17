import networkx as nx
from collections import defaultdict


def highway_type(data):
    """OSM highway tag for an edge, taking the first value when OSMnx stored a list."""
    h = data.get("highway")
    return h[0] if isinstance(h, list) else h


def to_simple_graph(G_multi):
    G_simple = nx.DiGraph()
    G_simple.add_nodes_from(G_multi.nodes(data=True))
    for u, v, data in G_multi.edges(data=True):
        length = float(data["length"])
        highway = highway_type(data)
        if G_simple.has_edge(u, v):
            if length < G_simple[u][v]["length"]:
                G_simple[u][v]["length"] = length
                G_simple[u][v]["highway"] = highway
        else:
            G_simple.add_edge(u, v, length=length, highway=highway)
    return G_simple

TRAIL_TYPES = {"path", "track", "bridleway", "footway", "pedestrian"}
ROAD_PENALTY = 15.0  # roads count as 15x their real distance for search purposes


def edge_cost(data):
    length = data["length"]
    if data.get("highway") in TRAIL_TYPES:
        return length
    return length * ROAD_PENALTY


def path_length(G, path):
    """Total length of a path given as a list of node IDs."""
    length = 0
    for u, v in zip(path[:-1], path[1:]):
        length += G[u][v]["length"]
    return length


def points_along_path(G, path, fractions):
    """
    Map positions at the given fractions (0-1, ascending) of a path's length.
    Interpolates linearly inside the edge where each fraction falls, so a
    point can land between nodes. Returns [{"lat", "lon", "at_m"}] in order.
    """
    total = path_length(G, path)
    points = []
    traveled = 0.0
    i = 0  # index of the edge (path[i], path[i+1]) being walked
    for f in fractions:
        target = f * total
        # Advance to the edge that contains target. The last edge absorbs
        # any floating-point overshoot at f == 1.
        while i < len(path) - 2 and traveled + G[path[i]][path[i + 1]]["length"] < target:
            traveled += G[path[i]][path[i + 1]]["length"]
            i += 1
        u, v = path[i], path[i + 1]
        edge = G[u][v]["length"]
        t = 0.0 if edge == 0 else min(max((target - traveled) / edge, 0.0), 1.0)
        points.append({
            "lat": G.nodes[u]["y"] + t * (G.nodes[v]["y"] - G.nodes[u]["y"]),
            "lon": G.nodes[u]["x"] + t * (G.nodes[v]["x"] - G.nodes[u]["x"]),
            "at_m": target,
        })
    return points


def highway_breakdown(G, path):
    """Meters of a path on each highway type, largest first. G is the simple graph."""
    totals = defaultdict(float)
    for u, v in zip(path[:-1], path[1:]):
        totals[G[u][v]["highway"]] += G[u][v]["length"]
    return sorted(totals.items(), key=lambda x: -x[1])


def get_bridges(G):
    """
    Undirected segments whose removal would split the network: cul-de-sacs,
    driveway and footpath stubs, and so on. A loop that never repeats a
    segment can't use one, since it could never get back across. About a
    quarter of the Madison graph's segments are bridges.

    Takes ~6s on the full regional graph, so it's computed once and cached on G.
    """
    if "bridges" not in G.graph:
        U = G.to_undirected(as_view=True)
        G.graph["bridges"] = {frozenset(e) for e in nx.bridges(U)}
    return G.graph["bridges"]


def precompute_distances_to_end(G, end_node, cutoff=None):
    """
    Real distance from every node to end_node. With a cutoff, nodes farther
    than that are left out, which keeps the search local to the route.
    """
    G_reversed = G.reverse(copy=False)
    return nx.single_source_dijkstra_path_length(G_reversed, end_node, cutoff=cutoff, weight="length")
