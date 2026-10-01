import osmnx as ox
from collections import defaultdict

from graph_utils import to_simple_graph
from pathfinding import find_path_with_restarts

G_multi = ox.load_graphml("madison_50mi_tiled_walk_network.graphml")
G = to_simple_graph(G_multi)

# Arboretum-adjacent start point
start_point = (43.0475, -89.4235)
end_point = (43.0850, -89.3900)  # same end as before

node_a = ox.distance.nearest_nodes(G_multi, start_point[1], start_point[0])
node_b = ox.distance.nearest_nodes(G_multi, end_point[1], end_point[0])

print(f"Node A: {node_a}, Node B: {node_b}")

path, length, steps = find_path_with_restarts(G, node_a, node_b, 8000, max_restarts=3)

if path is None:
    print("No path found")
else:
    def edge_highway(G_multi, u, v):
        edges = G_multi[u][v]
        best = min(edges.values(), key=lambda d: float(d["length"]))
        h = best.get("highway")
        return (h[0] if isinstance(h, list) else h), float(best["length"])

    totals = defaultdict(float)
    for u, v in zip(path[:-1], path[1:]):
        h, l = edge_highway(G_multi, u, v)
        totals[h] += l

    print(f"Route length: {length:.0f}m")
    for h, l in sorted(totals.items(), key=lambda x: -x[1]):
        print(f"{h}: {l:.0f}m ({l / length * 100:.0f}%)")