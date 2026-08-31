import osmnx as ox

G = ox.load_graphml("devils_lake_walk_network.graphml")

named_footways = set()
for u, v, data in G.edges(data=True):
    if data.get("highway") == "footway" and data.get("name"):
        name = data["name"]
        if isinstance(name, list):
            for n in name:
                named_footways.add(n)
        else:
            named_footways.add(name)

for name in sorted(named_footways):
    print(name)