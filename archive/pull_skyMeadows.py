import osmnx as ox

north, south, east, west = 39.020, 38.970, -77.940, -77.995

bbox = (west, south, east, north)

G_sky_meadows = ox.graph_from_bbox(bbox, network_type="walk")

print("Nodes:", len(G_sky_meadows.nodes))
print("Edges:", len(G_sky_meadows.edges))

ox.save_graphml(G_sky_meadows, filepath="sky_meadows_walk_network.graphml")