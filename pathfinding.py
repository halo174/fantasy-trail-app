import random
from graph_utils import precompute_distances_to_end, edge_cost


def find_path_matching_distance_dfs(G, start_node, end_node, target_distance, tolerance=0.2, max_steps=20000):
    """
    Randomized DFS with backtracking, guided by a Dijkstra-based feasibility
    bound on real distance. Among feasible neighbors, trail-type edges are
    weighted more heavily so the search prefers trails without ever ruling
    out roads outright.
    """
    dist_to_end = precompute_distances_to_end(G, end_node)

    if start_node not in dist_to_end:
        raise ValueError("end_node is not reachable from start_node")

    path = [start_node]
    visited = {start_node}
    traveled = [0.0]
    options_stack = []

    def get_valid_options(current, length_so_far):
        neighbors = list(G.neighbors(current))
        valid = []
        for n in neighbors:
            if n in visited:
                continue
            if n not in dist_to_end:
                continue
            data = G[current][n]
            edge_length = data["length"]
            remaining_budget = target_distance - (length_so_far + edge_length)
            if remaining_budget + (target_distance * tolerance) >= dist_to_end[n]:
                valid.append((n, edge_length, edge_cost(data)))
        return valid

    options_stack.append(get_valid_options(start_node, 0.0))

    best_path = None
    best_diff = float("inf")
    best_length = None
    steps = 0

    while path and steps < max_steps:
        steps += 1
        current = path[-1]
        current_length = traveled[-1]

        if current == end_node:
            diff = abs(current_length - target_distance)
            if diff < best_diff:
                best_diff = diff
                best_path = list(path)
                best_length = current_length
            if diff <= target_distance * tolerance:
                return best_path, best_length, steps
            visited.remove(path.pop())
            traveled.pop()
            options_stack.pop()
            continue

        if current_length > target_distance * (1 + tolerance) * 1.5:
            visited.remove(path.pop())
            traveled.pop()
            options_stack.pop()
            continue

        if not options_stack[-1]:
            visited.remove(path.pop())
            traveled.pop()
            options_stack.pop()
            continue

        options = options_stack[-1]
        weights = [1.0 / c for _, _, c in options]
        idx = random.choices(range(len(options)), weights=weights, k=1)[0]
        next_node, edge_length, _ = options.pop(idx)

        path.append(next_node)
        visited.add(next_node)
        new_length = current_length + edge_length
        traveled.append(new_length)
        options_stack.append(get_valid_options(next_node, new_length))

    if best_path is None:
        print(f"  No path found after {steps} steps")
        return None, None, steps

    return best_path, best_length, steps

def find_path_with_restarts(G, start_node, end_node, target_distance, tolerance=0.2, steps_per_attempt=20000, max_restarts=10):
    for attempt in range(max_restarts):
        path, length, steps = find_path_matching_distance_dfs(
            G, start_node, end_node, target_distance, tolerance, max_steps=steps_per_attempt
        )
        if path is not None:
            print(f"  Succeeded on restart {attempt + 1}, {steps} steps")
            return path, length, steps
    print(f"  Failed after {max_restarts} restarts")
    return None, None, None