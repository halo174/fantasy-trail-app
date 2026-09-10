import osmnx as ox

# Pick a small test area near you first — easier to inspect than the whole city
place_name = "Madison, Wisconsin, USA"

# Pull the walkable/trail network for that area
G = ox.graph_from_place(place_name, network_type="walk")

print("Nodes:", len(G.nodes))
print("Edges:", len(G.edges))

# Save it locally so you don't have to re-download every time you test
ox.save_graphml(G, filepath="madison_walk_network.graphml")
print("Saved graph to madison_walk_network.graphml")