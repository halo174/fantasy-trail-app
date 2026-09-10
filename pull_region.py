import osmnx as ox

# Center point: Madison, WI
center_point = (43.0731, -89.4012)

# Start smaller than 50 miles to keep this manageable while testing —
# ~15 miles ≈ 24,000 meters
radius_meters = 24000

G_regional = ox.graph_from_point(center_point, dist=radius_meters, network_type="walk")

print("Nodes:", len(G_regional.nodes))
print("Edges:", len(G_regional.edges))

ox.save_graphml(G_regional, filepath="madison_regional_walk_network.graphml")