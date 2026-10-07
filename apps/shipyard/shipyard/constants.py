"""Static EVE knowledge used by the catalog and the calculations."""

# --- Hull sizes by inventory group -------------------------------------------
HULL_GROUPS = {
    25: "Frigate",
    420: "Destroyer",
    26: "Cruiser",
    419: "Battlecruiser",   # Combat Battlecruiser
    1201: "Battlecruiser",  # Attack Battlecruiser
    27: "Battleship",
    463: "Barge",           # Mining Barge
    28: "Hauler",
}
HULL_ORDER = ["Frigate", "Destroyer", "Cruiser", "Battlecruiser", "Battleship", "Barge", "Hauler"]

# --- Factions -----------------------------------------------------------------
EMPIRE_FACTIONS = {
    500001: "Caldari State",
    500002: "Minmatar Republic",
    500003: "Amarr Empire",
    500004: "Gallente Federation",
}
PIRATE_FACTIONS = {
    500010: "Guristas Pirates",
    500011: "Angel Cartel",
    500012: "Blood Raider Covenant",
    500016: "Sisters of EVE",
    500018: "Mordu's Legion",
    500019: "Sansha's Nation",
    500020: "Serpentis",
    500029: "Deathless Circle",
}
ORE_FACTION = {500014: "ORE"}
TRIG_FACTION = {500026: "Triglavian Collective"}
EDENCOM_FACTION = {500027: "EDENCOM"}
OTHER_FACTIONS = {
    500006: "Jove Empire",
    500017: "Society of Conscious Thought",
}
FACTION_NAMES = {
    **EMPIRE_FACTIONS, **PIRATE_FACTIONS, **ORE_FACTION,
    **TRIG_FACTION, **EDENCOM_FACTION, **OTHER_FACTIONS,
}

# Short names shown in the Faction column
FACTION_SHORT = {
    500001: "Caldari", 500002: "Minmatar", 500003: "Amarr", 500004: "Gallente",
    500010: "Guristas", 500011: "Angel", 500012: "Blood Raiders", 500016: "SOE",
    500018: "Mordu's", 500019: "Sansha", 500020: "Serpentis", 500029: "Deathless",
    500014: "ORE", 500026: "Triglavian", 500027: "EDENCOM",
    500006: "Jove", 500017: "SoCT",
}

# Navy ships of each empire use the LP store of that empire's navy corp
NAVY_LP_STORE = {
    500001: "Caldari Navy",
    500002: "Republic Fleet",
    500003: "Imperial Navy",
    500004: "Federation Navy",
}

# --- Meta groups --------------------------------------------------------------
META_TECH_I = 1
META_FACTION = 4

# --- Categories (the "Type" column) ------------------------------------------
CAT_BASE = "Base"
CAT_NAVY = "Navy"
CAT_PIRATE = "Pirate"
CAT_TRIG = "Trig"
CAT_EDENCOM = "Edencom"
CAT_ORE = "ORE"
CAT_OTHER = "Other"
CATEGORY_ORDER = [CAT_BASE, CAT_NAVY, CAT_PIRATE, CAT_TRIG, CAT_EDENCOM, CAT_ORE, CAT_OTHER]

# Ships that exist with a blueprint entry but are not realistically buildable /
# not on the market as BPCs. Kept in the catalog, inactive by default.
INACTIVE_BY_DEFAULT = {
    "Apocalypse Imperial Issue", "Armageddon Imperial Issue",
    "Megathron Federate Issue", "Tempest Tribal Issue", "Raven State Issue",
    "Guardian-Vexor", "Stratios Emergency Responder",
    "Miasmos Amastris Edition", "Miasmos Quafe Ultra Edition",
    "Miasmos Quafe Ultramarine Edition", "Primae",
    "Gnosis", "Praxis", "Sunesis", "Metamorphosis", "Echelon",
    "Gold Magnate", "Silver Magnate", "Anhinga",
}

# --- Skills -------------------------------------------------------------------
SKILL_ACCOUNTING = 16622
SKILL_BROKER_RELATIONS = 3446
SKILL_INDUSTRY = 3380
SKILL_ADVANCED_INDUSTRY = 3388
SKILL_ADV_SMALL_SHIP = 3395
SKILL_ADV_MEDIUM_SHIP = 3396
SKILL_ADV_LARGE_SHIP = 3397
SKILL_ADV_INDUSTRIAL_SHIP = 3398

RELEVANT_SKILLS = {
    SKILL_ACCOUNTING: ("accounting", "Accounting", "−11 % sales tax per level"),
    SKILL_BROKER_RELATIONS: ("broker_relations", "Broker Relations", "−0.3 pp broker fee per level (NPC stations)"),
    SKILL_INDUSTRY: ("industry", "Industry", "−4 % build time per level"),
    SKILL_ADVANCED_INDUSTRY: ("advanced_industry", "Advanced Industry", "−3 % build time per level"),
    SKILL_ADV_SMALL_SHIP: ("adv_small_ship", "Advanced Small Ship Construction", "−1 % build time per level (frigates, destroyers)"),
    SKILL_ADV_MEDIUM_SHIP: ("adv_medium_ship", "Advanced Medium Ship Construction", "−1 % build time per level (cruisers, battlecruisers)"),
    SKILL_ADV_LARGE_SHIP: ("adv_large_ship", "Advanced Large Ship Construction", "−1 % build time per level (battleships)"),
    SKILL_ADV_INDUSTRIAL_SHIP: ("adv_industrial_ship", "Advanced Industrial Ship Construction", "−1 % build time per level (haulers, barges)"),
}

# EVE Ref cost API skill parameter names, keyed by our field names
EVEREF_SKILL_PARAMS = {
    "industry": "industry",
    "advanced_industry": "advanced_industry",
    "adv_small_ship": "advanced_small_ship_construction",
    "adv_medium_ship": "advanced_medium_ship_construction",
    "adv_large_ship": "advanced_large_ship_construction",
    "adv_industrial_ship": "advanced_industrial_ship_construction",
}

# --- Structures and rigs (seed data) -----------------------------------------
STRUCTURE_TYPES = {
    35825: "Raitaru",
    35826: "Azbel",
    35827: "Sotiyo",
    35832: "Astrahus",
    35833: "Fortizar",
    35834: "Keepstar",
    35835: "Athanor",
    35836: "Tatara",
}

# Standup M-Set (medium structure: Raitaru/Astrahus/Athanor) ship ME rigs
RIG_TYPES = {
    37154: "Standup M-Set Basic Small Ship Manufacturing Material Efficiency I",
    37155: "Standup M-Set Basic Small Ship Manufacturing Material Efficiency II",
    37146: "Standup M-Set Basic Medium Ship Manufacturing Material Efficiency I",
    37147: "Standup M-Set Basic Medium Ship Manufacturing Material Efficiency II",
    43732: "Standup M-Set Basic Large Ship Manufacturing Material Efficiency I",
    37152: "Standup M-Set Basic Large Ship Manufacturing Material Efficiency II",
    43855: "Standup M-Set Advanced Small Ship Manufacturing Material Efficiency I",
    43854: "Standup M-Set Advanced Small Ship Manufacturing Material Efficiency II",
    43858: "Standup M-Set Advanced Medium Ship Manufacturing Material Efficiency I",
    43859: "Standup M-Set Advanced Medium Ship Manufacturing Material Efficiency II",
    43862: "Standup M-Set Advanced Large Ship Manufacturing Material Efficiency I",
    43863: "Standup M-Set Advanced Large Ship Manufacturing Material Efficiency II",
    # L-Set (Azbel/Fortizar/Tatara) combined ME+TE rigs
    43714: "Standup L-Set Basic Small Ship Manufacturing Efficiency I",
    43715: "Standup L-Set Basic Small Ship Manufacturing Efficiency II",
    43716: "Standup L-Set Basic Medium Ship Manufacturing Efficiency I",
    43717: "Standup L-Set Basic Medium Ship Manufacturing Efficiency II",
    37166: "Standup L-Set Basic Large Ship Manufacturing Efficiency I",
    37167: "Standup L-Set Basic Large Ship Manufacturing Efficiency II",
    # XL-Set (Sotiyo/Keepstar)
    37180: "Standup XL-Set Ship Manufacturing Efficiency I",
    37181: "Standup XL-Set Ship Manufacturing Efficiency II",
}

# --- Markets ------------------------------------------------------------------
JITA_44_STATION_ID = 60003760
THE_FORGE_REGION_ID = 10000002
