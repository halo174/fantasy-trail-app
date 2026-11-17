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


def find_path_matching_distance_dfs(G, start_node, end_node, target_distance, tolerance=0.2, max_steps=20000, dist_to_end=None, slack=SEARCH_SLACK, forbidden_edges=frozenset()):
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

    forbidden_edges is a set of undirected segments (frozensets of two nodes)
    the route may not use, e.g. segments an earlier leg of the walk already took.
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
        edge = frozenset((current, n))
        if edge in forbidden_edges:
            return True
        if loop:
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


def find_path_with_restarts(G, start_node, end_node, target_distance, tolerance=0.2, steps_per_attempt=20000, max_restarts=10, slack=SEARCH_SLACK, forbidden_edges=frozenset()):
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
                steps_per_attempt, max_restarts, slack, forbidden_edges,
            )
            if loop is None:
                return None, None, steps
            return spur + loop[1:] + spur[-2::-1], loop_m + 2 * spur_m, steps

    return _search_with_restarts(
        G, start_node, end_node, target_distance, tolerance,
        steps_per_attempt, max_restarts, slack, forbidden_edges,
    )


def _search_with_restarts(G, start_node, end_node, target_distance, tolerance, steps_per_attempt, max_restarts, slack, forbidden_edges=frozenset()):
    # Same for every attempt, so compute it once instead of per restart
    dist_to_end = reachable_distances(G, start_node, end_node, target_distance, tolerance)
    total_steps = 0
    best_path, best_length = None, None
    for attempt in range(max_restarts):
        path, length, steps = find_path_matching_distance_dfs(
            G, start_node, end_node, target_distance, tolerance,
            max_steps=steps_per_attempt, dist_to_end=dist_to_end, slack=slack,
            forbidden_edges=forbidden_edges,
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

# How far into a leg's budget an anchor may sit (shortest distance, as a
# fraction of the leg). A near anchor is fine, the leg wanders to make up
# its distance; one near the very end leaves no slack to match it.
ANCHOR_WINDOW = (0.1, 0.9)
LEG_SEARCH = {"steps_per_attempt": 5000, "max_restarts": 15}
VIA_ATTEMPTS = 4


def find_route_via(G, start_node, end_node, target_distance, stops, anchors, tolerance=0.2):
    """
    A route of about target_distance that passes through a real place for
    each stop, in order, near the right distance into the walk.

    stops: [(stop, at_m)], at_m = how far into the walk the stop is due.
    anchors: {terrain: {node: place_name or None}} from features.find_anchors.
    Each stop's terrain is tried first, then its fallbacks (stop["terrains"]).

    The walk is chained as legs (start -> place -> place -> end). Each leg
    is a normal distance-matched search with its share of the distance, and
    may not reuse a segment an earlier leg took. Returns
    (path, length, steps, placements), with one placement per stop:
    {"node", "at_m", "terrain", "place_name"}, or None for a stop due right
    at the end of the walk, where there's no room to bend toward anything.
    Returns None if any leg can't be routed; the caller falls back to a
    plain route.
    """
    if start_node == end_node:
        # Same dead-end handling as plain loops: walk the stub out and back
        spur = loop_entry_path(G, start_node)
        if spur is None:
            return None
        if len(spur) > 1:
            spur_m = path_length(G, spur)
            junction = spur[-1]
            inner_target = target_distance - 2 * spur_m
            if inner_target <= 0:
                return None
            inner_stops = [(stop, max(at_m - spur_m, 0.0)) for stop, at_m in stops]
            inner = find_route_via(
                G, junction, junction, inner_target, inner_stops, anchors,
                tolerance=target_distance * tolerance / inner_target,
            )
            if inner is None:
                return None
            path, length, steps, placements = inner
            for p in placements:
                if p is not None:
                    p["at_m"] += spur_m
            return spur + path[1:] + spur[-2::-1], length + 2 * spur_m, steps, placements

    try:
        dist_to_end = reachable_distances(G, start_node, end_node, target_distance, tolerance)
    except UnreachableError:
        return None

    # Each attempt picks anchors at random, so a failed or short attempt can
    # succeed on a retry. Keep the closest in case none fits the distance.
    best = None
    for _ in range(VIA_ATTEMPTS):
        result = _route_via_once(G, start_node, end_node, target_distance, stops, anchors, dist_to_end, tolerance)
        if result is None:
            continue
        if within_tolerance(result[1], target_distance, tolerance):
            return result
        if best is None or abs(result[1] - target_distance) < abs(best[1] - target_distance):
            best = result
    return best


def _route_via_once(G, start_node, end_node, target_distance, stops, anchors, dist_to_end, tolerance):
    path = [start_node]
    traveled = 0.0
    used = set()
    total_steps = 0
    placements = []
    current = start_node

    for stop, at_m in stops:
        if target_distance - at_m < 100:
            # Due at the very end of the walk: it lands wherever the walk ends
            placements.append(None)
            continue
        leg_target = at_m - traveled
        remaining_after = target_distance - at_m
        candidates = _anchor_candidates(G, current, end_node, leg_target, remaining_after, stop, anchors, dist_to_end)

        for anchor, terrain in candidates[:3]:
            try:
                leg, leg_m, steps = find_path_with_restarts(
                    G, current, anchor, max(leg_target, 1.0), tolerance=0.25,
                    forbidden_edges=frozenset(used), **LEG_SEARCH,
                )
            except UnreachableError:
                continue
            total_steps += steps
            if leg is None:
                continue
            path += leg[1:]
            used.update(frozenset(e) for e in zip(leg[:-1], leg[1:]))
            traveled += leg_m
            current = anchor
            placements.append({
                "node": anchor, "at_m": traveled, "terrain": terrain,
                "place_name": anchors[terrain].get(anchor),
            })
            break
        else:
            return None

    # Last leg to the end takes whatever distance is left, so small misses
    # on earlier legs even out
    final_target = target_distance - traveled
    # For a loop with no stops placed yet, current is already the end node,
    # but the whole walk is still ahead of it
    if current != end_node or len(path) == 1:
        try:
            leg, leg_m, steps = find_path_with_restarts(
                G, current, end_node, max(final_target, 1.0),
                tolerance=target_distance * tolerance / max(final_target, 1.0),
                forbidden_edges=frozenset(used), **LEG_SEARCH,
            )
        except UnreachableError:
            return None
        total_steps += steps
        if leg is None:
            return None
        path += leg[1:]
        traveled += leg_m

    for i, p in enumerate(placements):
        if p is None:
            placements[i] = {"node": path[-1], "at_m": traveled, "terrain": None, "place_name": None}
    return path, traveled, total_steps, placements


def _anchor_candidates(G, current, end_node, leg_target, remaining_after, stop, anchors, dist_to_end):
    """
    Anchor nodes for a stop, best first: the stop's own terrain before its
    fallbacks, and within each terrain in random order. An anchor has to be
    reachable from the current point within the leg's budget, and close
    enough to the end that the rest of the walk can still get there.
    """
    lo, hi = ANCHOR_WINDOW
    if leg_target < 300:
        lo = 0.0  # a stop due almost immediately: anything close will do
    reach = nx.single_source_dijkstra_path_length(G, current, cutoff=leg_target * hi, weight="length")

    candidates = []
    for terrain in stop["terrains"]:
        nodes = [
            n for n in anchors.get(terrain, {})
            if n != current and n != end_node
            and lo * leg_target <= reach.get(n, float("inf")) <= hi * leg_target
            and dist_to_end.get(n, float("inf")) <= remaining_after * 0.9
        ]
        random.shuffle(nodes)
        # Named places first ("Gardner Marsh" beats an unnamed patch of woods)
        nodes.sort(key=lambda n: anchors[terrain][n] is None)
        candidates += [(n, terrain) for n in nodes]
    return candidates
