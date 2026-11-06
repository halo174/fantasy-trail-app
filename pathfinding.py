import heapq
import random
import networkx as nx
from graph_utils import precompute_distances_to_end, edge_cost, path_length, get_bridges

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

    When start_node == end_node it finds a loop. A loop can't be a simple path
    (it has to come back through the start), so in that mode the rule becomes
    "never walk the same street segment twice, in either direction" instead
    of "never visit the same node twice". Loops may cross their own
    intersections, but never retrace a segment.
    """
    if dist_to_end is None:
        dist_to_end = reachable_distances(G, start_node, end_node, target_distance, tolerance)

    # Never tighter than the shortest route itself, so targets just under it still work
    max_length = max(target_distance * (1 + slack), dist_to_end[start_node] * 1.01)

    loop = start_node == end_node
    bridges = get_bridges(G) if loop else None
    path = [start_node]
    visited = {start_node}   # point-to-point: nodes on the path
    used_edges = set()       # loop: undirected segments on the path
    traveled = [0.0]
    options_stack = []

    def blocked(current, n):
        if loop:
            edge = frozenset((current, n))
            return edge in used_edges or edge in bridges
        return n in visited

    def step_back():
        node = path.pop()
        if loop:
            if path:  # popping the start node itself has no edge to release
                used_edges.remove(frozenset((path[-1], node)))
        else:
            visited.remove(node)
        traveled.pop()
        options_stack.pop()

    def get_valid_options(current, length_so_far):
        neighbors = list(G.neighbors(current))
        valid = []
        for n in neighbors:
            if blocked(current, n):
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

        # len(path) > 1 so a loop isn't "finished" before it leaves the start
        if current == end_node and len(path) > 1:
            diff = abs(current_length - target_distance)
            if diff < best_diff:
                best_diff = diff
                best_path = list(path)
                best_length = current_length
            if within_tolerance(current_length, target_distance, tolerance):
                return best_path, best_length, steps
            step_back()
            continue

        if not options_stack[-1]:
            step_back()
            continue

        options = options_stack[-1]
        weights = [1.0 / c for _, _, c in options]
        idx = random.choices(range(len(options)), weights=weights, k=1)[0]
        next_node, edge_length, _ = options.pop(idx)

        path.append(next_node)
        if loop:
            used_edges.add(frozenset((current, next_node)))
        else:
            visited.add(next_node)
        new_length = current_length + edge_length
        traveled.append(new_length)
        options_stack.append(get_valid_options(next_node, new_length))

    if best_path is None:
        print(f"  No path found after {steps} steps")
        return None, None, steps

    return best_path, best_length, steps

def undirected_neighbors(G, node):
    return set(G.successors(node)) | set(G.predecessors(node))


def loop_entry_path(G, start_node):
    """
    Shortest path from start_node to the nearest node that sits on a cycle,
    i.e. has at least one non-bridge segment. A loop has to start from there.
    Every segment on this path is a bridge, so it's the only way in and out.
    Returns [start_node] if the start is already on a cycle, or None if no
    cycle is reachable at all.
    """
    bridges = get_bridges(G)

    def on_cycle(node):
        return any(frozenset((node, n)) not in bridges for n in undirected_neighbors(G, node))

    # Dijkstra that stops at the first node on a cycle. Usually only a few
    # hops, since dead-end stubs are short.
    dist = {start_node: 0.0}
    prev = {}
    tiebreak = 0  # so equal distances never fall back to comparing node IDs
    heap = [(0.0, tiebreak, start_node)]
    while heap:
        d, _, node = heapq.heappop(heap)
        if d > dist[node]:
            continue
        if on_cycle(node):
            path = [node]
            while path[-1] != start_node:
                path.append(prev[path[-1]])
            return path[::-1]
        for n in G.neighbors(node):
            nd = d + G[node][n]["length"]
            if nd < dist.get(n, float("inf")):
                dist[n] = nd
                prev[n] = node
                tiebreak += 1
                heapq.heappush(heap, (nd, tiebreak, n))
    return None


def find_path_with_restarts(G, start_node, end_node, target_distance, tolerance=0.2, steps_per_attempt=20000, max_restarts=10, slack=SEARCH_SLACK):
    """
    Returns as soon as an attempt lands within tolerance. Otherwise returns the
    closest route seen across all attempts (check it with within_tolerance),
    or None if no attempt reached the end at all.

    Loops that start on a dead-end stub (common, since clicks snap to the
    nearest OSM node) walk the stub out to the nearest node on a cycle, loop
    from there, and walk the stub back. That stub is the one stretch a loop is
    allowed to repeat, since there's no other way in or out.
    """
    if start_node == end_node:
        spur = loop_entry_path(G, start_node)
        if spur is None:
            print("  No cycle reachable from start, no loop possible")
            return None, None, 0
        if len(spur) > 1:
            spur_m = path_length(G, spur)
            junction = spur[-1]
            # Keep the acceptance window the same size in meters as the full route's
            inner_target = target_distance - 2 * spur_m
            if inner_target <= 0:
                print(f"  Target is shorter than the {spur_m * 2:.0f}m out-and-back to the nearest junction")
                return None, None, 0
            inner_tolerance = target_distance * tolerance / inner_target
            loop, loop_m, steps = _search_with_restarts(
                G, junction, junction, inner_target, inner_tolerance,
                steps_per_attempt, max_restarts, slack,
            )
            if loop is None:
                return None, None, steps
            return spur + loop[1:] + spur[-2::-1], loop_m + 2 * spur_m, steps

    return _search_with_restarts(
        G, start_node, end_node, target_distance, tolerance,
        steps_per_attempt, max_restarts, slack,
    )


def _search_with_restarts(G, start_node, end_node, target_distance, tolerance, steps_per_attempt, max_restarts, slack):
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