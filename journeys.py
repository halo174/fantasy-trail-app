"""
Example journeys a walk can follow.

Each stop's `at` is how far along the story's journey it falls, from 0 (the
start) to 1 (the end). A walk of any length places the stops at those same
fractions, so a 5km walk of the Odyssey reaches Circe's island at about 2.1km.

The fractions are rough. They come from story order and, where the story
has real or commonly estimated geography (Around the World in Eighty Days,
the Odyssey), approximate distances between places. They're meant to feel
right, not to be exact.

Every journey is from a public-domain work, except the one marked below.
"""

JOURNEYS = [
    {
        "id": "oz",
        "title": "The Road to Oz",
        "source": "L. Frank Baum, The Wonderful Wizard of Oz (1900), public domain",
        "blurb": "Follow the yellow brick road to the Emerald City, then find your way home.",
        "suggested_km": 5,
        "loop": True,  # there's no place like home
        "stops": [
            {"name": "Munchkin Country", "at": 0.0},
            {"name": "The Scarecrow's cornfield", "at": 0.06},
            {"name": "The Tin Woodman's cottage", "at": 0.12},
            {"name": "The Cowardly Lion's forest", "at": 0.18},
            {"name": "The Kalidahs' ravine", "at": 0.24},
            {"name": "The deadly poppy field", "at": 0.32},
            {"name": "The Emerald City", "at": 0.42},
            {"name": "The Wicked Witch's castle", "at": 0.56},
            {"name": "Back to the Emerald City", "at": 0.68},
            {"name": "The Dainty China Country", "at": 0.80},
            {"name": "Glinda's palace", "at": 0.92},
            {"name": "Home to Kansas", "at": 1.0},
        ],
    },
    {
        "id": "odyssey",
        "title": "The Long Way to Ithaca",
        "source": "Homer, The Odyssey (c. 8th century BC), public domain",
        "blurb": "Ten years, one ship, and every monster in the Mediterranean between you and home.",
        "suggested_km": 8,
        "loop": False,
        "stops": [
            {"name": "Troy", "at": 0.0},
            {"name": "Ismarus, land of the Cicones", "at": 0.05},
            {"name": "Land of the Lotus-Eaters", "at": 0.15},
            {"name": "The Cyclops' island", "at": 0.22},
            {"name": "Aeolus, keeper of the winds", "at": 0.30},
            {"name": "Circe's island", "at": 0.42},
            {"name": "The Land of the Dead", "at": 0.50},
            {"name": "The Sirens", "at": 0.58},
            {"name": "Scylla and Charybdis", "at": 0.63},
            {"name": "Calypso's island", "at": 0.80},
            {"name": "Phaeacia", "at": 0.92},
            {"name": "Ithaca", "at": 1.0},
        ],
    },
    {
        "id": "alice",
        "title": "Down the Rabbit Hole",
        "source": "Lewis Carroll, Alice's Adventures in Wonderland (1865), public domain",
        "blurb": "Chase a late rabbit through Wonderland and wake up back on the riverbank.",
        "suggested_km": 3,
        "loop": True,  # it was all a dream
        "stops": [
            {"name": "The riverbank", "at": 0.0},
            {"name": "Down the rabbit hole", "at": 0.08},
            {"name": "The pool of tears", "at": 0.20},
            {"name": "The White Rabbit's house", "at": 0.32},
            {"name": "The Caterpillar's mushroom", "at": 0.42},
            {"name": "The Duchess's kitchen", "at": 0.52},
            {"name": "The mad tea party", "at": 0.64},
            {"name": "The Queen's croquet ground", "at": 0.76},
            {"name": "The Mock Turtle's shore", "at": 0.86},
            {"name": "The trial of the Knave of Hearts", "at": 0.95},
            {"name": "Waking on the riverbank", "at": 1.0},
        ],
    },
    {
        "id": "west",
        "title": "Journey to the West",
        "source": "Wu Cheng'en, Journey to the West (16th century), public domain",
        "blurb": "Escort a monk, a monkey king, a pig and a river spirit to the scriptures in the west.",
        "suggested_km": 10,
        "loop": False,
        "stops": [
            {"name": "Chang'an", "at": 0.0},
            {"name": "Five Elements Mountain", "at": 0.10},
            {"name": "Eagle Grief Stream", "at": 0.15},
            {"name": "Gao Village", "at": 0.25},
            {"name": "Yellow Wind Ridge", "at": 0.32},
            {"name": "Flowing Sands River", "at": 0.38},
            {"name": "The Flaming Mountains", "at": 0.60},
            {"name": "Lion Camel Ridge", "at": 0.78},
            {"name": "Vulture Peak", "at": 1.0},
        ],
    },
    {
        "id": "eighty-days",
        "title": "Around the World in Eighty Days",
        "source": "Jules Verne, Around the World in Eighty Days (1872), public domain",
        "blurb": "A wager at the Reform Club: circle the globe and be back in London on time.",
        "suggested_km": 8,
        "loop": True,  # London to London
        # From approximate real distances along Fogg's route, about 38,000km in all
        "stops": [
            {"name": "London", "at": 0.0},
            {"name": "Suez", "at": 0.09},
            {"name": "Bombay", "at": 0.22},
            {"name": "Calcutta", "at": 0.27},
            {"name": "Hong Kong", "at": 0.42},
            {"name": "Yokohama", "at": 0.49},
            {"name": "San Francisco", "at": 0.71},
            {"name": "New York", "at": 0.85},
            {"name": "Liverpool", "at": 0.99},
            {"name": "London, just in time", "at": 1.0},
        ],
    },
    # NOT public domain. Uses place names only: no quotes, maps or art. Remove
    # this entry before showing the app publicly; nothing else depends on it.
    {
        "id": "fellowship",
        "title": "The Fellowship's Road",
        "source": "J.R.R. Tolkien, The Fellowship of the Ring (1954), place names only",
        "blurb": "From a hobbit hole in the Shire, south along the Great River.",
        "suggested_km": 8,
        "loop": False,
        "stops": [
            {"name": "Bag End", "at": 0.0},
            {"name": "Bree", "at": 0.12},
            {"name": "Weathertop", "at": 0.20},
            {"name": "Rivendell", "at": 0.40},
            {"name": "The gates of Moria", "at": 0.62},
            {"name": "Lothlórien", "at": 0.72},
            {"name": "The Argonath", "at": 0.95},
            {"name": "Amon Hen", "at": 1.0},
        ],
    },
]

JOURNEYS_BY_ID = {j["id"]: j for j in JOURNEYS}
