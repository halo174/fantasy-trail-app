import osmnx as ox
import networkx as nx

G = ox.load_graphml("sky_meadows_walk_network.graphml")

def trail_nodes(G, highway_types={"path", "track", "footway"}):
    matching_nodes = set()
    for u, v, data in G.edges(data=True):
        h = data.get("highway")
        types = h if isinstance(h, list) else [h]
        if any(t in highway_types for t in types):
            matching_nodes.add(u)
            matching_nodes.add(v)
    return matching_nodes

nodes = list(trail_nodes(G))

# Find the two nodes furthest apart by straight-line distance, so we get
# a meaningful start/end pair instead of two adjacent points
node_coords = {n: (G.nodes[n]["x"], G.nodes[n]["y"]) for n in nodes}

max_dist = 0
start_node, end_node = None, None
for i in range(len(nodes)):
    for j in range(i + 1, len(nodes)):
        n1, n2 = nodes[i], nodes[j]
        x1, y1 = node_coords[n1]
        x2, y2 = node_coords[n2]
        dist = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
        if dist > max_dist:
            max_dist = dist
            start_node, end_node = n1, n2

print(f"Start: {start_node}, End: {end_node}")

# Check they're actually connected before running distance-matching
if nx.has_path(G, start_node, end_node):
    print("Path exists between these nodes")
else:
    print("No path exists - need different nodes")