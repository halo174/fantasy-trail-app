import osmnx as ox

north, south, east, west = 43.455, 43.405, -89.700, -89.755

bbox = (west, south, east, north)

G_devils_lake = ox.graph_from_bbox(bbox, network_type="walk")

print("Nodes:", len(G_devils_lake.nodes))
print("Edges:", len(G_devils_lake.edges))

ox.save_graphml(G_devils_lake, filepath="devils_lake_walk_network.graphml")