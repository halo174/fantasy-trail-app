import osmnx as ox
import networkx as nx
import time

G_multi = ox.load_graphml("madison_regional_walk_network.graphml")

def to_simple_graph(G_multi):
    G_simple = nx.DiGraph()
    G_simple.add_nodes_from(G_multi.nodes(data=True))
    for u, v, data in G_multi.edges(data=True):
        length = float(data["length"])
        if G_simple.has_edge(u, v):
            if length < G_simple[u][v]["length"]:
                G_simple[u][v]["length"] = length
        else:
            G_simple.add_edge(u, v, length=length)
    return G_simple

start_time = time.time()
G = to_simple_graph(G_multi)
print(f"Simple graph conversion: {time.time() - start_time:.2f}s")

# Pick any node as a test "end_node"
test_end_node = list(G.nodes)[0]

start_time = time.time()
G_reversed = G.reverse()
dist_to_end = nx.single_source_dijkstra_path_length(G_reversed, test_end_node, weight="length")
print(f"Dijkstra precompute: {time.time() - start_time:.2f}s")
print(f"Reachable nodes: {len(dist_to_end)}")