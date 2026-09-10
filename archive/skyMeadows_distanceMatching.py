import osmnx as ox
import networkx as nx
import random
from itertools import islice

G_multi = ox.load_graphml("sky_meadows_walk_network.graphml")

total_length = sum(data["length"] for u, v, data in G_multi.edges(data=True))
print(f"Total edge length in graph: {total_length:.1f}m")


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

"""
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
"""

G = to_simple_graph(G_multi)

start_node = 1223855244
end_node = 13156822483

def precompute_distances_to_end(G, end_node):
    """
    Single Dijkstra run from end_node (on the reversed graph, since G is
    directed) giving shortest distance from every node to end_node.
    """
    G_reversed = G.reverse()
    return nx.single_source_dijkstra_path_length(G_reversed, end_node, weight="length")


def find_path_matching_distance_dfs(G, start_node, end_node, target_distance, tolerance=0.2, max_steps=2000000):
    dist_to_end = precompute_distances_to_end(G, end_node)

    if start_node not in dist_to_end:
        raise ValueError("end_node is not reachable from start_node")

    path = [start_node]
    visited = {start_node}
    traveled = [0.0]  # stack of cumulative distance at each path position
    # options[i] = shuffled list of untried (neighbor, edge_length) at path[i]
    options_stack = []

    def get_valid_options(current, traveled_so_far):
        neighbors = list(G.neighbors(current))
        valid = []
        for n in neighbors:
            if n in visited:
                continue
            if n not in dist_to_end:
                continue
            edge_length = G[current][n]["length"]
            remaining_budget = target_distance - (traveled_so_far + edge_length)
            if remaining_budget + (target_distance * tolerance) >= dist_to_end[n]:
                valid.append((n, edge_length))
        random.shuffle(valid)
        return valid

    options_stack.append(get_valid_options(start_node, 0.0))

    best_path = None
    best_diff = float("inf")
    best_length = None
    steps = 0

    while path and steps < max_steps:
        steps += 1
        current = path[-1]
        current_traveled = traveled[-1]

        if current == end_node:
            diff = abs(current_traveled - target_distance)
            if diff < best_diff:
                best_diff = diff
                best_path = list(path)
                best_length = current_traveled
            if diff <= target_distance * tolerance:
                return best_path, best_length, steps
            # even though we reached end_node, backtrack to look for a
            # better-matching route length
            visited.remove(path.pop())
            traveled.pop()
            options_stack.pop()
            continue

        if current_traveled > target_distance * (1 + tolerance) * 1.5:
            visited.remove(path.pop())
            traveled.pop()
            options_stack.pop()
            continue

        if not options_stack[-1]:
            # no more options here, backtrack
            visited.remove(path.pop())
            traveled.pop()
            options_stack.pop()
            continue

        next_node, edge_length = options_stack[-1].pop()
        path.append(next_node)
        visited.add(next_node)
        new_traveled = current_traveled + edge_length
        traveled.append(new_traveled)
        options_stack.append(get_valid_options(next_node, new_traveled))

    if best_path is None:
        print(f"  No path found after {steps} steps")
        return None, None, steps

    return best_path, best_length, steps


shortest = nx.shortest_path_length(G, start_node, end_node, weight="length")
print(f"Direct shortest path: {shortest:.1f}m")

for target in [shortest * 1.2, shortest * 2, shortest * 4]:
    print(f"\n--- Target: {target:.1f}m ---")
    path, length, steps = find_path_matching_distance_dfs(G, start_node, end_node, target)
    if path is None:
        print("Failed to find any valid path")
    else:
        print(f"Found: {length:.1f}m after {steps} steps")