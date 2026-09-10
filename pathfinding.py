import random
from graph_utils import precompute_distances_to_end


def find_path_matching_distance_dfs(G, start_node, end_node, target_distance, tolerance=0.2, max_steps=20000):
    """
    Randomized DFS with backtracking, guided by a Dijkstra-based feasibility
    bound, to find a simple path from start_node to end_node whose length
    is close to target_distance.
    """
    dist_to_end = precompute_distances_to_end(G, end_node)

    if start_node not in dist_to_end:
        raise ValueError("end_node is not reachable from start_node")

    path = [start_node]
    visited = {start_node}
    traveled = [0.0]
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