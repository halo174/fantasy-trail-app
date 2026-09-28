import time
import osmnx as ox
import networkx as nx

from graph_utils import to_simple_graph
from pathfinding import find_path_with_restarts

G_multi = ox.load_graphml("madison_50mi_tiled_walk_network.graphml")
G = to_simple_graph(G_multi)

point_a = (43.0455, -89.4128)  # near the Arboretum
point_b = (43.0850, -89.3900)  # a few miles northeast

node_a = ox.distance.nearest_nodes(G_multi, point_a[1], point_a[0])
node_b = ox.distance.nearest_nodes(G_multi, point_b[1], point_b[0])

print(f"Node A: {node_a}, Node B: {node_b}")

shortest = nx.shortest_path_length(G, node_a, node_b, weight="length")
print(f"Direct shortest: {shortest:.1f}m")

target = shortest * 1.5

start_time = time.time()
path, length, steps = find_path_with_restarts(G, node_a, node_b, target)
if path is not None:
    print(f"Search took {time.time() - start_time:.2f}s, found {length:.1f}m after {steps} steps")
else:
    print(f"Failed to find valid path after {time.time() - start_time:.2f}s")

for target in [20000, 30000]:
    print(f"\n--- Target: {target}m ---")
    start_time = time.time()
    path, length, steps = find_path_with_restarts(G, node_a, node_b, target)
    print(f"Total time: {time.time() - start_time:.2f}s")
    if path is not None:
        print(f"Found: {length:.1f}m")