import osmnx as ox

ox.settings.requests_timeout = 600;

center_point = (43.0731, -89.4012)  # Madison, WI

radius_meters = 80467  # 50 miles

G_full = ox.graph_from_point(center_point, dist=radius_meters, network_type="walk")

print("Nodes:", len(G_full.nodes))
print("Edges:", len(G_full.edges))

ox.save_graphml(G_full, filepath="madison_50mi_walk_network.graphml")