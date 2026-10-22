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


def highway_breakdown(G, path):
    """Meters of a path on each highway type, largest first. G is the simple graph."""
    totals = defaultdict(float)
    for u, v in zip(path[:-1], path[1:]):
        totals[G[u][v]["highway"]] += G[u][v]["length"]
    return sorted(totals.items(), key=lambda x: -x[1])


def precompute_distances_to_end(G, end_node, cutoff=None):
    """
    Real distance from every node to end_node. With a cutoff, nodes farther
    than that are left out, which keeps the search local to the route.
    """
    G_reversed = G.reverse(copy=False)
    return nx.single_source_dijkstra_path_length(G_reversed, end_node, cutoff=cutoff, weight="length")
