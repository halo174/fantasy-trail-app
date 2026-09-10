import networkx as nx


def to_simple_graph(G_multi):
    """Convert a MultiDiGraph to a simple DiGraph, keeping the shortest edge
    when multiple parallel edges exist between the same two nodes."""
    G_simple = nx.DiGraph()
    G_simple.add_nodes_from(G_multi.nodes(data=True))
    for u, v, data in G_multi.edges(data=True):
        length = float(data["length"])
        if G_simple.has_edge(u, v):
            if length < G_simple[u][v]["length"]:
                G_simple[u][v]["length"] = length
        else:
            G_simple.add_edge(u, v, length=length)
    return G_simple


def path_length(G, path):
    """Total length of a path given as a list of node IDs."""
    length = 0
    for u, v in zip(path[:-1], path[1:]):
        length += G[u][v]["length"]
    return length


def precompute_distances_to_end(G, end_node):
    """Single Dijkstra run from end_node (on the reversed graph, since G is
    directed) giving shortest distance from every node to end_node."""
    G_reversed = G.reverse()
    return nx.single_source_dijkstra_path_length(G_reversed, end_node, weight="length")