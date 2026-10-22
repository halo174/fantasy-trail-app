import osmnx as ox
import networkx as nx

from graph_utils import highway_type

G_multi = ox.load_graphml("madison_50mi_tiled_walk_network.graphml")

# Stricter than graph_utils.TRAIL_TYPES on purpose: footway/pedestrian are left
# out so this measures how connected "real" trail is on its own (README numbers)
STRICT_TRAIL_TYPES = {"path", "track", "bridleway"}

trail_edges = [
    (u, v, k) for u, v, k, data in G_multi.edges(keys=True, data=True)
    if highway_type(data) in STRICT_TRAIL_TYPES
]

G_trail = G_multi.edge_subgraph(trail_edges).copy()

print(f"Trail-only graph: {len(G_trail.nodes)} nodes, {len(G_trail.edges)} edges")

components = list(nx.weakly_connected_components(G_trail))
components.sort(key=len, reverse=True)
print(f"Number of connected components: {len(components)}")
print("Largest 5 component sizes:", [len(c) for c in components[:5]])
