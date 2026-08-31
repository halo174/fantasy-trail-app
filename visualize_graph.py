import osmnx as ox

G = ox.load_graphml("devils_lake_walk_network.graphml")
ox.plot_graph(G, node_size=2, edge_linewidth=0.5)