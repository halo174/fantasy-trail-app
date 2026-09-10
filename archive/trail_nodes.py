import osmnx as ox
import networkx as nx


G = ox.load_graphml("devils_lake_walk_network.graphml")

def nodes_on_trail(G, trail_name):
    matching_nodes = set()
    for u, v, data in G.edges(data=True):
        name = data.get("name")
        names = name if isinstance(name, list) else [name]
        if trail_name in names:
            matching_nodes.add(u)
            matching_nodes.add(v)
    return matching_nodes

east_bluff_nodes = nodes_on_trail(G, "East Bluff Trail")
west_bluff_nodes = nodes_on_trail(G, "West Bluff Trail")

start_node = list(east_bluff_nodes)[0]
end_node = list(west_bluff_nodes)[0]

route = nx.shortest_path(G, start_node, end_node, weight="length")
route_length = nx.shortest_path_length(G, start_node, end_node, weight="length")

print(f"Path has {len(route)} nodes")
print(f"Total length: {route_length:.1f} meters")

ox.plot_graph_route(G, route, node_size=2)

