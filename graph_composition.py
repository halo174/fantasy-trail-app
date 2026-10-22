import osmnx as ox
from collections import defaultdict

from graph_utils import highway_type

G_multi = ox.load_graphml("madison_50mi_tiled_walk_network.graphml")

totals = defaultdict(float)
for u, v, data in G_multi.edges(data=True):
    totals[highway_type(data)] += float(data["length"])

grand = sum(totals.values())
for h, l in sorted(totals.items(), key=lambda x: -x[1])[:12]:
    print(f"{h}: {l / 1000:.0f}km ({l / grand * 100:.1f}%)")
