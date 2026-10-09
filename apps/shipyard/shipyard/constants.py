"""Static EVE knowledge used by the catalog and the calculations."""

# --- Hull sizes by inventory group -------------------------------------------
HULL_GROUPS = {
    25: "Frigate",
    420: "Destroyer",
    26: "Cruiser",
    419: "Battlecruiser",   # Combat Battlecruiser
    1201: "Battlecruiser",  # Attack Battlecruiser
    27: "Battleship",
    463: "Barge",           # Mining Barge (kept apart from the industrials, owner's wish)
    28: "Industrial",       # Haulers incl. Noctis
    941: "Industrial",      # Industrial Command Ships: Porpoise (Orca inactive by default)
}
HULL_ORDER = ["Frigate", "Destroyer", "Cruiser", "Battlecruiser", "Battleship", "Barge", "Industrial"]

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
CAT_FUEL = "Fuel"  # fuel blocks: their own tab, not on the ship dashboard
CATEGORY_ORDER = [CAT_BASE, CAT_NAVY, CAT_PIRATE, CAT_TRIG, CAT_EDENCOM, CAT_ORE, CAT_OTHER]

# Fuel blocks (owner, 2026-10-09): built from the corp's own BPOs, 40 blocks per run
FUEL_GROUP_ID = 1136
FUEL_UNITS_PER_RUN = 40

# Researched corp BPOs (owner, 2026-10-09): base hulls and fuel blocks are priced at ME 10 / TE 20;
# everything else at ME 0 unless the member owns a blueprint for it.
RESEARCHED_ME_TE = {CAT_BASE: (10, 20), CAT_FUEL: (10, 20)}

# --- Blueprint policy (owner's decision 2026-10-07): who provides the blueprint ----
# free:   the corp hands the copy out for nothing (T1 hulls, BPOs are cheap and owned).
# corp:   the corp buys the copy in the LP store and sells it on at cost + markup.
# public: the corp has no source; members find copies on public contracts, so the
#         blueprint is left OUT of the cost and the net profit is marked as such.
# manual: whatever price is typed on the Blueprints page.
BPC_FREE, BPC_CORP, BPC_PUBLIC, BPC_MANUAL = "free", "corp", "public", "manual"
BPC_POLICY = {
    CAT_BASE: BPC_FREE,
    CAT_NAVY: BPC_CORP,
    CAT_PIRATE: BPC_PUBLIC,
    CAT_TRIG: BPC_PUBLIC,
    CAT_EDENCOM: BPC_PUBLIC,
    CAT_ORE: BPC_MANUAL,
    CAT_OTHER: BPC_MANUAL,
    CAT_FUEL: BPC_FREE,  # own BPO
}
# Exceptions by hull: base battleships are not newbro ships; by then members source
# their own blueprints on the Jita market (owner's decision 2026-10-07).
BPC_POLICY_BY_HULL = {
    (CAT_BASE, "Battleship"): BPC_PUBLIC,
}
# Exceptions by ship name (win over the type and hull rules).
BPC_POLICY_BY_NAME = {
    "Perseverance": BPC_PUBLIC,  # ORE destroyer, blueprint only on public contracts (owner, 2026-10-07)
}


def bpc_policy(category, hull_size=None, name=None):
    """Who provides the blueprint for a ship of this type, hull size and name."""
    if category is None:
        return BPC_MANUAL
    if name in BPC_POLICY_BY_NAME:
        return BPC_POLICY_BY_NAME[name]
    return BPC_POLICY_BY_HULL.get((category, hull_size), BPC_POLICY.get(category, BPC_MANUAL))

# Ships that exist with a blueprint entry but are not realistically buildable /
# not on the market as BPCs. Kept in the catalog, inactive by default.
INACTIVE_BY_DEFAULT = {
    "Orca",  # in the catalog because Porpoise shares its group; switch on in the admin if wanted
    "Pioneer Consortium Issue", "Venture Consortium Issue",  # special editions, not for this dashboard (owner, 2026-10-08)
    "Apocalypse Imperial Issue", "Armageddon Imperial Issue",
    "Megathron Federate Issue", "Tempest Tribal Issue", "Raven State Issue",
    "Guardian-Vexor", "Stratios Emergency Responder",
    "Miasmos Amastris Edition", "Miasmos Quafe Ultra Edition",
    "Miasmos Quafe Ultramarine Edition", "Primae",
    "Gnosis", "Praxis", "Sunesis", "Metamorphosis", "Echelon",
    "Gold Magnate", "Silver Magnate", "Anhinga",
}

# --- ESI scopes: "everything" (owner's decision 2026-10-07) ------------------------
# The full set Member Audit asks for; characters.full_scopes() prefers Member Audit's own
# list at runtime so the two never drift apart. 33 scopes.
FULL_SCOPES = [
    "esi-assets.read_assets.v1",
    "esi-calendar.read_calendar_events.v1",
    "esi-characters.read_agents_research.v1",
    "esi-characters.read_blueprints.v1",
    "esi-characters.read_contacts.v1",
    "esi-characters.read_corporation_roles.v1",
    "esi-characters.read_fatigue.v1",
    "esi-characters.read_fw_stats.v1",
    "esi-characters.read_loyalty.v1",
    "esi-characters.read_medals.v1",
    "esi-characters.read_notifications.v1",
    "esi-characters.read_standings.v1",
    "esi-characters.read_titles.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-corporations.read_corporation_membership.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_character_mining.v1",
    "esi-killmails.read_killmails.v1",
    "esi-location.read_location.v1",
    "esi-location.read_online.v1",
    "esi-location.read_ship_type.v1",
    "esi-mail.read_mail.v1",
    "esi-markets.read_character_orders.v1",
    "esi-markets.structure_markets.v1",
    "esi-planets.manage_planets.v1",
    "esi-planets.read_customs_offices.v1",
    "esi-search.search_structures.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-skills.read_skills.v1",
    "esi-universe.read_structures.v1",
    "esi-wallet.read_character_wallet.v1",
]

# --- ESI scopes: "everything" (owner's decision 2026-10-07) ------------------------
# The full set Member Audit asks for; characters.full_scopes() prefers Member Audit's own
# list at runtime so the two never drift apart. 33 scopes.
FULL_SCOPES = [
    "esi-assets.read_assets.v1",
    "esi-calendar.read_calendar_events.v1",
    "esi-characters.read_agents_research.v1",
    "esi-characters.read_blueprints.v1",
    "esi-characters.read_contacts.v1",
    "esi-characters.read_corporation_roles.v1",
    "esi-characters.read_fatigue.v1",
    "esi-characters.read_fw_stats.v1",
    "esi-characters.read_loyalty.v1",
    "esi-characters.read_medals.v1",
    "esi-characters.read_notifications.v1",
    "esi-characters.read_standings.v1",
    "esi-characters.read_titles.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-corporations.read_corporation_membership.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-industry.read_character_mining.v1",
    "esi-killmails.read_killmails.v1",
    "esi-location.read_location.v1",
    "esi-location.read_online.v1",
    "esi-location.read_ship_type.v1",
    "esi-mail.read_mail.v1",
    "esi-markets.read_character_orders.v1",
    "esi-markets.structure_markets.v1",
    "esi-planets.manage_planets.v1",
    "esi-planets.read_customs_offices.v1",
    "esi-search.search_structures.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-skills.read_skills.v1",
    "esi-universe.read_structures.v1",
    "esi-wallet.read_character_wallet.v1",
]

# --- Industry activities and job slots -----------------------------------------
ACTIVITIES = {
    1: "Manufacturing", 3: "TE research", 4: "ME research", 5: "Copying",
    8: "Invention", 9: "Reactions", 11: "Reactions",
}
MANUFACTURING_ACTIVITIES = {1, 9, 11}
# Mass Production, Advanced Mass Production; Laboratory Operation, Advanced Laboratory Operation
SLOT_SKILLS = {"manufacturing": (3387, 24625), "science": (3406, 24624)}
SLOT_SKILLS_ALL = tuple(s for group in SLOT_SKILLS.values() for s in group)

# --- Skills -------------------------------------------------------------------
SKILL_ACCOUNTING = 16622
SKILL_BROKER_RELATIONS = 3446
SKILL_INDUSTRY = 3380
SKILL_ADVANCED_INDUSTRY = 3388
SKILL_ADV_SMALL_SHIP = 3395
SKILL_ADV_MEDIUM_SHIP = 3396
SKILL_ADV_LARGE_SHIP = 3397
SKILL_ADV_INDUSTRIAL_SHIP = 3398
SKILL_SCRAPMETAL = 12196

RELEVANT_SKILLS = {
    SKILL_ACCOUNTING: ("accounting", "Accounting", "−11 % sales tax per level"),
    SKILL_BROKER_RELATIONS: ("broker_relations", "Broker Relations", "−0.3 pp broker fee per level (NPC stations)"),
    SKILL_INDUSTRY: ("industry", "Industry", "−4 % build time per level"),
    SKILL_ADVANCED_INDUSTRY: ("advanced_industry", "Advanced Industry", "−3 % build time per level"),
    SKILL_ADV_SMALL_SHIP: ("adv_small_ship", "Advanced Small Ship Construction", "−1 % build time per level (frigates, destroyers)"),
    SKILL_ADV_MEDIUM_SHIP: ("adv_medium_ship", "Advanced Medium Ship Construction", "−1 % build time per level (cruisers, battlecruisers)"),
    SKILL_ADV_LARGE_SHIP: ("adv_large_ship", "Advanced Large Ship Construction", "−1 % build time per level (battleships)"),
    SKILL_ADV_INDUSTRIAL_SHIP: ("adv_industrial_ship", "Advanced Industrial Ship Construction", "−1 % build time per level (haulers, barges)"),
    SKILL_SCRAPMETAL: ("scrapmetal_processing", "Scrapmetal Processing", "+2 % module reprocessing yield per level (Scrapmetal tab)"),
}

# --- Scrapmetal tab: the modules the owner buys to reprocess (2026-10-08) --------------
# (group label, exact in-game names). Order = the owner's in-game folder order (alphabetical by his folder
# names: 100mn, 1600, 500mn, 800mm, clutch, EM hard, EXP hard, grapple, hull, kin hard, large guns, mega electron,
# mega ion, mega neutron, neut, nos, pulse, remote shiebo, smartbomb, therm hard), so lines match the game. Managers add more in the admin.
SCRAP_GROUPS = [
    ("100MN afterburners", [
        "100MN Monopropellant Enduring Afterburner",
        "100MN Y-S8 Compact Afterburner",
    ]),
    ("1600mm plates", [
        "1600mm Crystalline Carbonide Restrained Plates",
        "1600mm Rolled Tungsten Compact Plates",
    ]),
    ("500MN microwarpdrives", [
        "500MN Cold-Gas Enduring Microwarpdrive",
        "500MN Quad LiF Restrained Microwarpdrive",
        "500MN Y-T8 Compact Microwarpdrive",
    ]),
    ("800mm plates", [
        "800mm Crystalline Carbonide Restrained Plates",
        "800mm Rolled Tungsten Compact Plates",
    ]),
    ("Warp disruption field generators", [
        "Clutch Restrained Warp Disruption Field Generator",
        "M-36 Enduring Warp Disruption Field Generator",
        "Pitfall Compact Warp Disruption Field Generator",
    ]),
    ("EM armor hardeners", [
        "Experimental Enduring EM Armor Hardener I",
        "Prototype Compact EM Armor Hardener I",
    ]),
    ("Explosive armor hardeners", [
        "Experimental Enduring Explosive Armor Hardener I",
        "Prototype Compact Explosive Armor Hardener I",
    ]),
    ("Heavy stasis grapplers", [
        "Heavy Gunnar Compact Stasis Grappler",
        "Heavy Jigoro Enduring Stasis Grappler",
        "Heavy Karelin Scoped Stasis Grappler",
    ]),
    ("Large hull repairers", [
        "Large 'Hope' Hull Reconstructor I",
        "Large Automated Structural Restoration",
        "Large I-b Polarized Structural Regenerator",
        "Large Inefficient Hull Repair Unit",
    ]),
    ("Kinetic armor hardeners", [
        "Experimental Enduring Kinetic Armor Hardener I",
        "Prototype Compact Kinetic Armor Hardener I",
    ]),
    ("Large guns (1400mm, 425mm, Tachyon)", [
        "1400mm Carbine Howitzer I",
        "1400mm Gallium Cannon",
        "1400mm Prototype Siege Cannon",
        "425mm 'Scout' Accelerator Cannon",
        "425mm Carbide Railgun I",
        "425mm Compressed Coil Gun I",
        "425mm Prototype Gauss Gun",
        "Tachyon Afocal Laser I",
        "Tachyon Anode Particle Stream I",
        "Tachyon Modal Laser I",
    ]),
    ("Mega electron blasters", [
        "Anode Mega Electron Particle Cannon I",
        "Limited Electron Blaster Cannon I",
        "Modal Mega Electron Particle Accelerator I",
        "Regulated Mega Electron Phase Cannon I",
    ]),
    ("Mega ion blasters", [
        "Limited Mega Ion Blaster I",
        "Modal Mega Ion Particle Accelerator I",
        "Regulated Mega Ion Phase Cannon I",
    ]),
    ("Mega neutron blasters", [
        "Anode Mega Neutron Particle Cannon I",
        "Limited Mega Neutron Blaster I",
        "Modal Mega Neutron Particle Accelerator I",
        "Regulated Mega Neutron Phase Cannon I",
    ]),
    ("Heavy energy neutralizers", [
        "Heavy Gremlin Compact Energy Neutralizer",
        "Heavy Infectious Scoped Energy Neutralizer",
    ]),
    ("Heavy energy nosferatus", [
        "Heavy Ghoul Compact Energy Nosferatu",
        "Heavy Knave Scoped Energy Nosferatu",
    ]),
    ("Mega pulse lasers", [
        "Mega Afocal Pulse Laser I",
        "Mega Anode Pulse Particle Stream I",
        "Mega Modal Pulse Laser I",
    ]),
    ("Large remote shield boosters", [
        "Large Asymmetric Enduring Remote Shield Booster",
        "Large Murky Compact Remote Shield Booster",
        "Large S95a Scoped Remote Shield Booster",
    ]),
    ("Smartbombs", [
        "'Concussion' Compact Large Graviton Smartbomb",
        "'Concussion' Compact Medium Graviton Smartbomb",
        "'Notos' Compact Large Proton Smartbomb",
        "'Notos' Compact Medium Proton Smartbomb",
        "'Vehemence' Compact Large EMP Smartbomb",
        "'Vehemence' Compact Medium EMP Smartbomb",
        "'YF-12a' Compact Large Plasma Smartbomb",
        "'YF-12a' Compact Medium Plasma Smartbomb",
    ]),
    ("Thermal armor hardeners", [
        "Experimental Enduring Thermal Armor Hardener I",
        "Prototype Compact Thermal Armor Hardener I",
    ]),
    ("Metal scraps", [  # owner, 2026-10-08: below the thermal hardeners
        "Metal Scraps",
        "Reinforced Metal Scraps",
    ]),
]

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
