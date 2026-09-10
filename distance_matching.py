import osmnx as ox
import networkx as nx
from itertools import islice

G_multi = ox.load_graphml("devils_lake_walk_network.graphml")


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


G = to_simple_graph(G_multi)


def nodes_on_trail(G, trail_name):
    matching_nodes = set()
    for u, v, data in G.edges(data=True):
        name = data.get("name")
        names = name if isinstance(name, list) else [name]
        if trail_name in names:
            matching_nodes.add(u)
            matching_nodes.add(v)
    return matching_nodes


def path_length(G, path):
    length = 0
    for u, v in zip(path[:-1], path[1:]):
        length += G[u][v]["length"]
    return length


def find_path_matching_distance(G, start_node, end_node, target_distance, tolerance=0.2, max_candidates=50):
    """
    Search simple paths from start_node to end_node, in increasing order of
    length, and return the one closest to target_distance.

    tolerance: acceptable fractional distance from target (0.2 = within 20%)
    max_candidates: how many candidate paths to check before giving up
    """
    best_path = None
    best_diff = float("inf")

    path_generator = nx.shortest_simple_paths(G, start_node, end_node, weight="length")

    for path in islice(path_generator, max_candidates):
        length = path_length(G, path)
        diff = abs(length - target_distance)

        if diff < best_diff:
            best_diff = diff
            best_path = path
            best_length = length

        # Early exit if we're within tolerance
        if diff <= target_distance * tolerance:
            return path, length

        # Once candidate paths start getting longer than target, no point continuing
        if length > target_distance * (1 + tolerance) * 2:
            break

    return best_path, best_length


if __name__ == "__main__":
    east_bluff_nodes = nodes_on_trail(G_multi, "East Bluff Trail")
    west_bluff_nodes = nodes_on_trail(G_multi, "West Bluff Trail")

    start_node = list(east_bluff_nodes)[0]
    end_node = list(west_bluff_nodes)[0]

    target_distance = 10000  # meters - try adjusting this

    path, length = find_path_matching_distance(G, start_node, end_node, target_distance)

    print(f"Target: {target_distance}m, Found: {length:.1f}m")
    print(f"Path has {len(path)} nodes")

    ox.plot_graph_route(G_multi, path, node_size=2)