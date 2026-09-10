import osmnx as ox
import networkx as nx

G = ox.load_graphml("devils_lake_walk_network.graphml")

# Pick two arbitrary nodes to start - we'll refine to real trailhead locations next
nodes = list(G.nodes)
start_node = nodes[0]
end_node = nodes[len(nodes) // 2]

# Run Dijkstra's shortest path, weighted by edge length
route = nx.shortest_path(G, start_node, end_node, weight="length")
route_length = nx.shortest_path_length(G, start_node, end_node, weight="length")

print(f"Path has {len(route)} nodes")
print(f"Total length: {route_length:.1f} meters")

# Visualize the route on the graph
ox.plot_graph_route(G, route, node_size=2)