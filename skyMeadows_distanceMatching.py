import osmnx as ox
import networkx as nx
from itertools import islice

G_multi = ox.load_graphml("sky_meadows_walk_network.graphml")


def to_simple_graph(G_multi):
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
    length = 0
    for u, v in zip(path[:-1], path[1:]):
        length += G[u][v]["length"]
    return length


def find_path_matching_distance(G, start_node, end_node, target_distance, tolerance=0.2, max_candidates=50):
    best_path = None
    best_diff = float("inf")
    candidates_checked = 0

    path_generator = nx.shortest_simple_paths(G, start_node, end_node, weight="length")

    for path in islice(path_generator, max_candidates):
        candidates_checked += 1
        length = path_length(G, path)
        diff = abs(length - target_distance)

        if diff < best_diff:
            best_diff = diff
            best_path = path
            best_length = length

        if diff <= target_distance * tolerance:
            print(f"Checked {candidates_checked} candidates, found match within tolerance")
            return path, length

        if length > target_distance * (1 + tolerance) * 2:
            print(f"Checked {candidates_checked} candidates, stopped early (path getting too long)")
            break

    print(f"Checked {candidates_checked} candidates total, returning closest")
    return best_path, best_length


G = to_simple_graph(G_multi)

start_node = 1223855244
end_node = 13156822483

shortest = nx.shortest_path_length(G, start_node, end_node, weight="length")
print(f"Direct shortest path: {shortest:.1f}m")

for target in [shortest * 1.2, shortest * 2, shortest * 4]:
    print(f"\n--- Target: {target:.1f}m ---")
    path, length = find_path_matching_distance(G, start_node, end_node, target)
    print(f"Found: {length:.1f}m")