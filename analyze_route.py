import osmnx as ox

from graph_utils import to_simple_graph, highway_breakdown
from pathfinding import find_path_with_restarts

G_multi = ox.load_graphml("madison_50mi_tiled_walk_network.graphml")
G = to_simple_graph(G_multi)

node_a = 53519815
node_b = 2705148674

path, length, steps = find_path_with_restarts(G, node_a, node_b, 8000, max_restarts=3)

if path is None:
    print("No path found")
else:
    print(f"Route length: {length:.0f}m")
    for h, l in highway_breakdown(G, path):
        print(f"{h}: {l:.0f}m ({l / length * 100:.0f}%)")
