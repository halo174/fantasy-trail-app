import osmnx as ox

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
print(f"Found {len(nodes)} trail nodes")

ox.plot_graph(G, node_size=5, edge_linewidth=1)