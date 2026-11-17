"""
Journeys walked at their real story length, over as many walks as it takes.

Each stop's `km` is its distance from the journey's start, using the
best published figures for each story. Each walk covers the next stretch:
if you've walked 730km of Frodo's road, a 10km walk today passes
Rivendell at 735km.

`terrain` is the kind of real place a stop should land on, when one is
nearby (see features.TERRAINS): Lothlórien in real woods, Moria at a real
tunnel or underpass, and so on.

NOT PUBLIC DOMAIN: both journeys are from Tolkien's works. They use place
names only (no quotes, maps or art), for personal use. Remove them before
showing this app publicly.
"""

JOURNEYS = [
    {
        "id": "frodo",
        "title": "Frodo's Road",
        "source": "J.R.R. Tolkien, The Lord of the Rings (1954-55), place names only",
        "blurb": "From Bag End to the fires of Mount Doom, the long way round.",
        "total_km": 2865,
        # Stage distances from Karen Wynn Fonstad, The Atlas of Middle-earth
        # (rev. ed., 1991), measured on Tolkien's maps, as tabulated at
        # https://lord-of-the-steps.ru/en/blog/frodos-route. The 2,865km
        # (~1,779mi) total matches the Eowyn Challenge figure from the Atlas.
        "distance_note": "Stage distances from Fonstad's Atlas of Middle-earth.",
        "stops": [
            {"name": "Bag End", "km": 0, "terrain": "town"},
            {"name": "Bucklebury Ferry", "km": 115, "terrain": "water"},
            {"name": "Bree", "km": 215, "terrain": "town"},
            {"name": "Weathertop", "km": 385, "terrain": "hill"},
            {"name": "Rivendell", "km": 735, "terrain": "water"},
            {"name": "The gates of Moria", "km": 1285, "terrain": "tunnel"},
            {"name": "Lothlórien", "km": 1480, "terrain": "forest"},
            {"name": "Amon Hen", "km": 2105, "terrain": "hill"},
            {"name": "The Dead Marshes", "km": 2360, "terrain": "marsh"},
            {"name": "Minas Morgul", "km": 2640, "terrain": "tower"},
            {"name": "Cirith Ungol", "km": 2675, "terrain": "tunnel"},
            {"name": "Mount Doom", "km": 2865, "terrain": "hill"},
        ],
    },
    {
        "id": "bilbo",
        "title": "Bilbo's Road",
        "source": "J.R.R. Tolkien, The Hobbit (1937), place names only",
        "blurb": "There and back again, or at least there: Bag End to the Lonely Mountain.",
        "total_km": 1529,
        # Total 950mi (1,529km) and Bag End to Rivendell 397mi (639km) from
        # LOTRProject, as reported at https://www.theonering.net/torwp/2014/05/31/
        # 89705-compare-the-time-and-distance-travelled-in-the-hobbit-and-the-lord-of-the-rings
        # No published source gives the other stages, so those stops are
        # estimates from their positions on Tolkien's map.
        "distance_note": "Total and Rivendell from LOTRProject; other stops estimated from the map.",
        "stops": [
            {"name": "Bag End", "km": 0, "terrain": "town"},
            {"name": "The Trollshaws", "km": 560, "terrain": "forest"},
            {"name": "Rivendell", "km": 639, "terrain": "water"},
            {"name": "Goblin-town", "km": 750, "terrain": "tunnel"},
            {"name": "Beorn's hall", "km": 900, "terrain": "meadow"},
            {"name": "Mirkwood", "km": 1000, "terrain": "forest"},
            {"name": "The Elvenking's halls", "km": 1250, "terrain": "tunnel"},
            {"name": "Lake-town", "km": 1440, "terrain": "water"},
            {"name": "The Lonely Mountain", "km": 1529, "terrain": "hill"},
        ],
    },
]

JOURNEYS_BY_ID = {j["id"]: j for j in JOURNEYS}


def stops_due(journey, progress_km, walk_km):
    """Stops reached on a walk of walk_km starting at progress_km, never the start stop."""
    end_km = progress_km + walk_km
    return [s for s in journey["stops"] if progress_km < s["km"] <= end_km + 1e-9]


def next_stop(journey, progress_km):
    """The first stop still ahead after progress_km, or None when the journey is done."""
    for s in journey["stops"]:
        if s["km"] > progress_km + 1e-9:
            return s
    return None
