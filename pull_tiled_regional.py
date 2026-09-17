import osmnx as ox
import networkx as nx
import time

ox.settings.requests_timeout = 300

center_point = (43.0731, -89.4012)  # Madison, WI
full_radius = 80467  # 50 miles in meters
tile_radius = 20000  # ~12 miles per tile, small enough to reliably succeed

# Generate a grid of tile centers covering the full radius, with overlap
import math

def generate_tile_centers(center, full_radius, tile_radius, overlap_factor=0.7):
    lat, lon = center
    step = tile_radius * overlap_factor * 2  # step distance in meters
    tiles = []

    # Convert step to rough degrees (good enough approximation for tiling)
    meters_per_deg_lat = 111000
    meters_per_deg_lon = 111000 * math.cos(math.radians(lat))

    steps_needed = int(full_radius / step) + 1

    for dx in range(-steps_needed, steps_needed + 1):
        for dy in range(-steps_needed, steps_needed + 1):
            tile_lat = lat + (dy * step) / meters_per_deg_lat
            tile_lon = lon + (dx * step) / meters_per_deg_lon
            dist_from_center = math.sqrt((dx * step) ** 2 + (dy * step) ** 2)
            if dist_from_center <= full_radius:
                tiles.append((tile_lat, tile_lon))

    return tiles

tile_centers = generate_tile_centers(center_point, full_radius, tile_radius)
print(f"Generated {len(tile_centers)} tiles to pull")

graphs = []
failed_tiles = []

for i, (tile_lat, tile_lon) in enumerate(tile_centers):
    print(f"Pulling tile {i + 1}/{len(tile_centers)} at ({tile_lat:.4f}, {tile_lon:.4f})...")
    try:
        G_tile = ox.graph_from_point((tile_lat, tile_lon), dist=tile_radius, network_type="walk")
        graphs.append(G_tile)
        print(f"  Got {len(G_tile.nodes)} nodes, {len(G_tile.edges)} edges")
    except Exception as e:
        print(f"  Failed: {e}")
        failed_tiles.append((tile_lat, tile_lon))
    time.sleep(2)  # be polite to the free server, avoid rate limiting

print(f"\nSuccessfully pulled {len(graphs)}/{len(tile_centers)} tiles")
print(f"Failed tiles: {len(failed_tiles)}")

# Retry failed tiles once, with a longer pause
if failed_tiles:
    print("\nRetrying failed tiles...")
    still_failed = []
    for tile_lat, tile_lon in failed_tiles:
        time.sleep(5)
        try:
            G_tile = ox.graph_from_point((tile_lat, tile_lon), dist=tile_radius, network_type="walk")
            graphs.append(G_tile)
            print(f"  Retry succeeded: {len(G_tile.nodes)} nodes")
        except Exception as e:
            print(f"  Retry failed: {e}")
            still_failed.append((tile_lat, tile_lon))
    failed_tiles = still_failed

print(f"\nFinal: {len(graphs)} tiles merged, {len(failed_tiles)} permanently failed")

G_merged = nx.compose_all(graphs)
print(f"Merged graph: {len(G_merged.nodes)} nodes, {len(G_merged.edges)} edges")

ox.save_graphml(G_merged, filepath="madison_50mi_tiled_walk_network.graphml")