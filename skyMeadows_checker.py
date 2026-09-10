import osmnx as ox
from collections import Counter

G = ox.load_graphml("sky_meadows_walk_network.graphml")

highway_types = [data.get("highway") for u, v, data in G.edges(data=True)]
counts = Counter(str(h) for h in highway_types)

for highway_type, count in counts.most_common():
    print(f"{highway_type}: {count}")