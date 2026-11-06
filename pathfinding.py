import random
import networkx as nx
from graph_utils import precompute_distances_to_end, edge_cost

# Routes end almost exactly at target * (1 + slack). Benchmarked 0.02-0.2 on
# 1.5x-5x targets: success rate and trail % were the same, so keep it tight.
SEARCH_SLACK = 0.02


class UnreachableError(ValueError):
    """
    No route fits the target. shortest_m is the shortest possible route,
    or None if the end can't be reached from the start at all.
    """
    def __init__(self, shortest_m):
        self.shortest_m = shortest_m
        if shortest_m is None:
            msg = "end_node is not reachable from start_node"
        else:
            msg = f"shortest route is {shortest_m:.0f}m, longer than the target allows"
        super().__init__(msg)


def within_tolerance(length, target_distance, tolerance=0.2):
    return abs(length - target_distance) <= target_distance * tolerance


def reachable_distances(G, start_node, end_node, target_distance, tolerance=0.2):
    """
    Distances to end_node, cut off at the longest route the search accepts.
    Nodes beyond the cutoff could never pass the feasibility check anyway.
    """
    dist_to_end = precompute_distances_to_end(G, end_node, cutoff=target_distance * (1 + tolerance))
    if start_node not in dist_to_end:
        # Only on failure: find out whether the target was too short or there's no route at all
        try:
            shortest = nx.shortest_path_length(G, start_node, end_node, weight="length")
        except nx.NetworkXNoPath:
            shortest = None
        raise UnreachableError(shortest)
    return dist_to_end


def find_path_matching_distance_dfs(G, start_node, end_node, target_distance, tolerance=0.2, max_steps=20000, dist_to_end=None, slack=SEARCH_SLACK):
    """
    Randomized DFS with backtracking, guided by a Dijkstra-based feasibility
    bound on real distance. Among feasible neighbors, trail-type edges are
    weighted more heavily so the search prefers trails without ever ruling
    out roads outright.

    The walk keeps wandering until the feasibility bound forces it toward the
    end, so routes land near that bound. Using a smaller slack than the
    acceptance tolerance keeps them close to the target instead of at +tolerance.
    """
    if dist_to_end is None:
        dist_to_end = reachable_distances(G, start_node, end_node, target_distance, tolerance)

    # Never tighter than the shortest route itself, so targets just under it still work
    max_length = max(target_distance * (1 + slack), dist_to_end[start_node] * 1.01)

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
            if length_so_far + edge_length + dist_to_end[n] <= max_length:
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
            if within_tolerance(current_length, target_distance, tolerance):
                return best_path, best_length, steps
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

def find_path_with_restarts(G, start_node, end_node, target_distance, tolerance=0.2, steps_per_attempt=20000, max_restarts=10, slack=SEARCH_SLACK):
    """
    Returns as soon as an attempt lands within tolerance. Otherwise returns the
    closest route seen across all attempts (check it with within_tolerance),
    or None if no attempt reached the end at all.
    """
    # Same for every attempt, so compute it once instead of per restart
    dist_to_end = reachable_distances(G, start_node, end_node, target_distance, tolerance)
    total_steps = 0
    best_path, best_length = None, None
    for attempt in range(max_restarts):
        path, length, steps = find_path_matching_distance_dfs(
            G, start_node, end_node, target_distance, tolerance,
            max_steps=steps_per_attempt, dist_to_end=dist_to_end, slack=slack,
        )
        total_steps += steps
        if path is None:
            continue
        if within_tolerance(length, target_distance, tolerance):
            print(f"  Succeeded on restart {attempt + 1}, {total_steps} total steps")
            return path, length, total_steps
        if best_path is None or abs(length - target_distance) < abs(best_length - target_distance):
            best_path, best_length = path, length
    if best_path is not None:
        print(f"  No route within tolerance after {max_restarts} restarts, closest is {best_length:.0f}m")
    else:
        print(f"  Failed after {max_restarts} restarts")
    return best_path, best_length, total_steps