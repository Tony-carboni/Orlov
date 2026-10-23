from django.conf import settings
from django.db import models
from django.utils import timezone

from . import constants


class General(models.Model):
    """Permission holder only (no table)."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("basic_access", "Can access the Shipyard dashboard"),
            ("reprocessing_access", "Can use the Reprocessing tab only (no other Shipyard pages)"),
            ("dashboard_access", "Can use the ship dashboard and My settings only (no other Shipyard pages)"),
            ("manage_shipyard", "Can edit blueprint prices, LP prices and facilities"),
            ("view_corp_industry", "Can see the industry of everyone in their corporation"),
            ("view_alliance_industry", "Can see the industry of everyone in the alliance"),
            ("books_access", "Can see the corporation's balance sheet (Finance tab)"),
        )


class Facility(models.Model):
    """A preset manufacturing location: structure + rigs + system + tax."""

    name = models.CharField(max_length=100, unique=True)
    structure_type_id = models.PositiveIntegerField(
        help_text="EVE type ID of the structure (Raitaru 35825, Azbel 35826, Sotiyo 35827, Astrahus 35832, Athanor 35835)"
    )
    structure_name = models.CharField(max_length=50)
    system_id = models.PositiveIntegerField(help_text="Solar system ID (Isikano 30001387)")
    system_name = models.CharField(max_length=50)
    rig_type_ids = models.JSONField(default=list, blank=True, help_text="List of rig type IDs fitted")
    facility_tax = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, help_text="Facility tax set by the structure owner, in %"
    )
    manufacturing_index = models.FloatField(default=0, help_text="System manufacturing cost index (fraction), refreshed from ESI")
    index_updated_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_default", "name"]
        verbose_name_plural = "facilities"

    def __str__(self):
        return self.name

    @property
    def rig_names(self):
        return [constants.RIG_TYPES.get(int(r), f"Rig {r}") for r in (self.rig_type_ids or [])]

    @property
    def is_npc_station(self):
        return self.structure_type_id == 0


class MarketLocation(models.Model):
    """Where the member buys materials and sells the ship (prices + taxes)."""

    name = models.CharField(max_length=100, unique=True)
    station_id = models.PositiveBigIntegerField(help_text="Station or structure ID (Jita 4-4: 60003760)")
    region_id = models.PositiveIntegerField(default=constants.THE_FORGE_REGION_ID)
    is_npc_station = models.BooleanField(default=True)
    owner_corporation_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="NPC corporation that owns the station (Jita 4-4: Caldari Navy 1000035); the member's standing with it lowers the broker fee",
    )
    owner_faction_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Faction of that corporation (Caldari State 500001); the member's standing with it lowers the broker fee",
    )
    sales_tax_base = models.DecimalField(
        max_digits=5, decimal_places=3, default=7.5,
        help_text="Base sales tax in % before Accounting skill (NPC stations: 7.5)",
    )
    broker_fee_base = models.DecimalField(
        max_digits=5, decimal_places=3, default=3.0,
        help_text="Base broker fee in % (NPC station 3.0 before Broker Relations; player structure: owner-set)",
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_default", "name"]

    def __str__(self):
        return self.name


class LpFaction(models.Model):
    """ISK value of one loyalty point for a faction's LP store."""

    name = models.CharField(max_length=100, unique=True)
    isk_per_lp = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="What a member pays per LP, in ISK")
    notes = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "LP faction"

    def __str__(self):
        return self.name


class Ship(models.Model):
    """A buildable T1 / faction hull."""

    type_id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    group_id = models.PositiveIntegerField()
    hull_size = models.CharField(max_length=20)
    category = models.CharField(max_length=20)
    faction_id = models.PositiveIntegerField(null=True, blank=True)
    faction_name = models.CharField(max_length=50, blank=True)
    meta_group_id = models.PositiveIntegerField(null=True, blank=True)
    blueprint_type_id = models.PositiveIntegerField()
    units_per_run = models.PositiveIntegerField(default=1, help_text="Products per blueprint run (40 for fuel blocks)")

    @property
    def default_me_te(self) -> tuple[int, int]:
        """ME/TE the dashboard assumes without a member's own blueprint (constants.RESEARCHED_ME_TE)."""
        return constants.RESEARCHED_ME_TE.get(self.category, (0, 0))
    volume = models.FloatField(default=0, help_text="Packaged volume m³")
    is_active = models.BooleanField(default=True, help_text="Shown on the dashboard")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def faction_short(self):
        return constants.FACTION_SHORT.get(self.faction_id, self.faction_name)


class ShipConfig(models.Model):
    """Hand-maintained inputs per ship: blueprint and tag prices, LP offer."""

    ship = models.OneToOneField(Ship, on_delete=models.CASCADE, related_name="config")
    bpc_price_isk = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Blueprint cost per run (ISK), bought on the market")
    tag_cost_isk = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="Other extra inputs per run (ISK), typed by hand")
    tag_type_id = models.PositiveIntegerField(null=True, blank=True, help_text="EVE type ID of a tag or other item the LP store offer needs; priced at the market's lowest sell at every refresh")
    tag_quantity = models.PositiveSmallIntegerField(default=1, help_text="How many of that item one copy needs")
    lp_faction = models.ForeignKey(LpFaction, null=True, blank=True, on_delete=models.SET_NULL)
    lp_cost = models.PositiveIntegerField(default=0, help_text="LP for one blueprint copy in the LP store")
    lp_isk_cost = models.DecimalField(max_digits=15, decimal_places=2, default=0, help_text="ISK part of the LP store offer")
    lp_runs = models.PositiveIntegerField(default=1, help_text="Runs on the copy from the LP store")
    notes = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Config {self.ship}"

    @property
    def has_lp_offer(self):
        return bool(self.lp_faction_id and self.lp_cost)

    def lp_bpc_price_per_run(self):
        if not self.has_lp_offer:
            return None
        runs = max(1, self.lp_runs)
        total = float(self.lp_cost) * float(self.lp_faction.isk_per_lp) + float(self.lp_isk_cost)
        return total / runs

    def tag_cost(self, tag_unit_price=None) -> tuple[float, bool]:
        """Per-run cost of tags and extras, and whether the tag's market price was missing.

        The hand-typed extras always count. A tag type is priced at `tag_unit_price`
        (the market's lowest sell, looked up by the caller) times the quantity, spread
        over the runs of the copy, like the LP price.
        """
        total = float(self.tag_cost_isk or 0)
        if not self.tag_type_id:
            return total, False
        if tag_unit_price is None:
            return total, True
        runs = max(1, self.lp_runs)
        return total + float(tag_unit_price) * self.tag_quantity / runs, False


class MemberBlueprintPrice(models.Model):
    """A blueprint price one member typed for themselves (right-click on the dashboard's Blueprint cell).

    It replaces the corp's policy figure in that member's numbers only. It is the whole
    copy as the member can get it, so no tags or markup are added on top.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shipyard_bpc_prices")
    ship = models.ForeignKey(Ship, on_delete=models.CASCADE, related_name="member_prices")
    price_isk = models.DecimalField(max_digits=15, decimal_places=2, help_text="Blueprint cost per run (ISK) as this member gets it")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "ship")]

    def __str__(self):
        return f"{self.user} {self.ship}: {self.price_isk}"


class ContractPrice(models.Model):
    """Blueprint copy price per ship from public contracts (services/contracts.py).

    price_per_run is the owner's figure: the average per-run price of the cheapest
    SHIPYARD_CONTRACT_RUNS runs on offer. `offers` keeps the cheapest contracts for the
    tooltip. Rows older than SHIPYARD_CONTRACT_MAX_AGE_HOURS are ignored.
    """

    ship = models.OneToOneField(Ship, on_delete=models.CASCADE, related_name="contract_price")
    price_per_run = models.DecimalField(max_digits=15, decimal_places=2)
    lowest_per_run = models.DecimalField(max_digits=15, decimal_places=2)
    runs_used = models.PositiveIntegerField(default=0, help_text="Runs that went into the average")
    offers_used = models.PositiveIntegerField(default=0, help_text="Contracts that went into the average")
    contracts = models.PositiveIntegerField(default=0, help_text="Matching contracts in the snapshot")
    runs_available = models.PositiveIntegerField(default=0, help_text="Runs on offer in all matching contracts")
    offers = models.JSONField(default=list, blank=True, help_text="The cheapest contracts: price, runs, ME/TE, station")
    snapshot_at = models.DateTimeField(help_text="EVE Ref scrape time of the snapshot")
    fetched_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.ship}: {self.price_per_run} per run from contracts"


class Ore(models.Model):
    """A compressed ore or ice type and what it reprocesses into (services/reprocessing.py)."""

    type_id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    group_id = models.PositiveIntegerField()
    group_name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, help_text="ore | ice | moon | abyssal")
    family = models.CharField(max_length=100, help_text="Base ore this is a variant of, e.g. Gneiss")
    variant = models.CharField(max_length=10, default="base", help_text="base | 0 | II | III | IV | X (grade in the name) | +15 | +100 (moon ore)")
    portion_size = models.PositiveIntegerField(default=1)
    volume = models.FloatField(default=0, help_text="m³ per unit")
    materials = models.JSONField(default=dict, help_text="{material type id: quantity per portion}")
    skill_id = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["kind", "family", "variant"]

    def __str__(self):
        return self.name

    MOON_RARITY = {"ubiquitous": "R4", "common": "R8", "uncommon": "R16", "rare": "R32", "exceptional": "R64"}

    @property
    def rarity(self) -> str:
        """Moon ore rarity from the group name ("Common Moon Asteroids" → "R8"); empty for other ores."""
        if self.kind != "moon":
            return ""
        first = self.group_name.split(" ", 1)[0].lower()
        return self.MOON_RARITY.get(first, "")


class ScrapItem(models.Model):
    """A module the owner buys to reprocess, and what it gives (services/scrapmetal.py)."""

    type_id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    group = models.CharField(max_length=60, default="Other", help_text="Group shown on the Scrapmetal tab, e.g. 'Smartbombs'")
    group_order = models.PositiveIntegerField(default=999)
    variant = models.CharField(max_length=12, default="other", help_text="Compact | Enduring | Scoped | Restrained | Ample | other, from the name")
    meta_level = models.PositiveSmallIntegerField(default=0)
    portion_size = models.PositiveIntegerField(default=1)
    volume = models.FloatField(default=0, help_text="Packaged m³ per unit")
    materials = models.JSONField(default=dict, help_text="{material type id: quantity per unit before yield}")
    is_active = models.BooleanField(default=True)
    avg_daily_volume = models.FloatField(default=0)
    avg_price = models.FloatField(default=0)
    stats_fetched_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["group_order", "group", "name"]

    def __str__(self):
        return self.name


class OreMarketStats(models.Model):
    """Regional history aggregates for a compressed ore (same shape as ShipMarketStats)."""

    ore = models.OneToOneField(Ore, on_delete=models.CASCADE, related_name="market_stats")
    region_id = models.PositiveIntegerField(default=constants.THE_FORGE_REGION_ID)
    avg_daily_volume = models.FloatField(default=0)
    avg_price = models.FloatField(default=0)
    days = models.PositiveSmallIntegerField(default=7)
    fetched_at = models.DateTimeField(default=timezone.now)


class WalletDivision(models.Model):
    """A wallet division of the structure corp: name and last balance (services/wallet.py)."""

    corporation_id = models.PositiveIntegerField()
    division = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100, blank=True)
    balance = models.FloatField(default=0)
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("corporation_id", "division")]


class WalletJournalEntry(models.Model):
    """Our own copy of the structure corp's wallet journal (ESI only serves the recent part)."""

    entry_id = models.BigIntegerField(primary_key=True)
    corporation_id = models.PositiveIntegerField(db_index=True)
    division = models.PositiveSmallIntegerField()
    date = models.DateTimeField(db_index=True)
    ref_type = models.CharField(max_length=60, db_index=True)
    amount = models.FloatField(default=0)
    balance = models.FloatField(default=0)
    first_party_id = models.BigIntegerField(default=0, db_index=True)
    first_party_name = models.CharField(max_length=100, blank=True)
    first_party_corp_id = models.BigIntegerField(default=0)
    first_party_corp_name = models.CharField(max_length=100, blank=True)
    second_party_id = models.BigIntegerField(default=0)
    second_party_name = models.CharField(max_length=100, blank=True)
    context_id = models.BigIntegerField(default=0)
    context_id_type = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=500, blank=True)
    reason = models.CharField(max_length=500, blank=True)
    tax = models.FloatField(default=0)
    tax_receiver_id = models.BigIntegerField(default=0)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date:%Y-%m-%d} {self.ref_type} {self.amount:,.0f}"


class LpOffer(models.Model):
    """One offer of a loyalty point store (ESI /loyalty/stores/{corp}/offers/, services/lpstore.py)."""

    store_corp_id = models.PositiveIntegerField(db_index=True)
    offer_id = models.PositiveIntegerField()
    type_id = models.PositiveIntegerField(db_index=True)
    quantity = models.PositiveIntegerField(default=1)
    lp_cost = models.PositiveIntegerField(default=0)
    isk_cost = models.FloatField(default=0)
    ak_cost = models.PositiveIntegerField(default=0)
    required_items = models.JSONField(default=list, blank=True, help_text="[[type id, quantity], ...] handed in with the LP")
    fetched_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["store_corp_id", "offer_id"]
        unique_together = [("store_corp_id", "offer_id")]

    def __str__(self):
        return f"offer {self.offer_id}: {self.quantity} x {self.type_id} for {self.lp_cost} LP"


class LpTypeMarket(models.Model):
    """Name and Jita market figures of every type an LP store touches (outputs and inputs)."""

    type_id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    is_blueprint = models.BooleanField(default=False)
    sell_min = models.FloatField(null=True, blank=True)
    sell_volume = models.FloatField(default=0)
    sell_orders = models.PositiveIntegerField(default=0)
    buy_max = models.FloatField(null=True, blank=True)
    avg_daily_volume = models.FloatField(default=0)
    prices_at = models.DateTimeField(null=True, blank=True)
    volume_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class CorpJournalEntry(models.Model):
    """The executor corp's wallet journal (services/ledger.py). Its own table because EVE gives a transfer
    between two corporations the same entry id in both journals (the structure corp's job tax, a donation),
    so one table keyed on the entry id alone made the two ledgers overwrite each other (fixed in 0.14.1)."""

    corporation_id = models.PositiveIntegerField(db_index=True)
    entry_id = models.BigIntegerField()
    division = models.PositiveSmallIntegerField()
    date = models.DateTimeField(db_index=True)
    ref_type = models.CharField(max_length=60, db_index=True)
    amount = models.FloatField(default=0)
    balance = models.FloatField(default=0)
    first_party_id = models.BigIntegerField(default=0)
    second_party_id = models.BigIntegerField(default=0)
    context_id = models.BigIntegerField(default=0)
    context_id_type = models.CharField(max_length=40, blank=True)
    description = models.CharField(max_length=500, blank=True)
    reason = models.CharField(max_length=500, blank=True)
    tax = models.FloatField(default=0)
    tax_receiver_id = models.BigIntegerField(default=0)

    class Meta:
        ordering = ["-date"]
        # a transfer between two wallet divisions carries the same entry id in both journals (0.17.1)
        unique_together = [("corporation_id", "division", "entry_id")]

    def __str__(self):
        return f"{self.date:%Y-%m-%d} {self.ref_type} {self.amount:,.0f}"


class CorpWalletTransaction(models.Model):
    """A market transaction of a corporation wallet division (ESI keeps a month; services/ledger.py keeps it all).
    Used to match the executor corp's sales against what its projects bought from members."""

    transaction_id = models.BigIntegerField(primary_key=True)
    corporation_id = models.PositiveIntegerField(db_index=True)
    division = models.PositiveSmallIntegerField()
    date = models.DateTimeField(db_index=True)
    type_id = models.PositiveIntegerField(db_index=True)
    quantity = models.BigIntegerField(default=0)
    unit_price = models.FloatField(default=0)
    is_buy = models.BooleanField(default=False)
    client_id = models.BigIntegerField(default=0)
    location_id = models.BigIntegerField(default=0)
    journal_ref_id = models.BigIntegerField(default=0)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date:%Y-%m-%d} {'buy' if self.is_buy else 'sell'} {self.quantity} x {self.type_id}"


class WalletExcludedPayer(models.Model):
    """A payer whose entries are left out of the Structure income figures (owner, 2026-10-15):
    the tax is still charged in game, the ledger still holds the entries, only the totals, the
    per-period tables and the charts skip them. Toggled with the checkbox in "Who pays"."""

    corporation_id = models.PositiveIntegerField(db_index=True)
    party_id = models.BigIntegerField()
    party_name = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=150, blank=True)

    class Meta:
        unique_together = [("corporation_id", "party_id")]

    def __str__(self):
        return f"{self.party_name or self.party_id} left out of income"


class CorpProject(models.Model):
    """A corporation project as last seen (services/projects.py); history in the snapshots."""

    project_id = models.CharField(max_length=40, primary_key=True)
    corporation_id = models.PositiveIntegerField(db_index=True)
    name = models.CharField(max_length=200)
    state = models.CharField(max_length=20, blank=True)
    kind = models.CharField(max_length=40, blank=True, help_text="deliver_item, mine_material, manufacture_item, destroy_ship, manual, …")
    career = models.CharField(max_length=30, blank=True)
    description = models.CharField(max_length=1000, blank=True)
    creator_id = models.BigIntegerField(default=0)
    creator_name = models.CharField(max_length=100, blank=True)
    created = models.DateTimeField(null=True, blank=True)
    expires = models.DateTimeField(null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)
    progress_current = models.BigIntegerField(default=0)
    progress_desired = models.BigIntegerField(default=0)
    reward_initial = models.FloatField(default=0)
    reward_remaining = models.FloatField(default=0)
    reward_per_contribution = models.FloatField(default=0)
    details = models.JSONField(default=dict, blank=True)
    last_modified = models.DateTimeField(null=True, blank=True)
    last_seen = models.DateTimeField(default=timezone.now)
    missing = models.BooleanField(default=False, help_text="No longer returned by ESI")

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return self.name

    @property
    def paid_out(self) -> float:
        """ISK members earned: units delivered x reward per unit (capped by the pool). Not the pool going down,
        because closing a project refunds what is left to the corp wallet (0.14.0)."""
        if self.state == "Deleted" and not self.contributions.exists():
            return 0.0  # deleted before anyone delivered; the journal shows the pool refunded in full
        earned = self.progress_current * (self.reward_per_contribution or 0)
        return max(0.0, min(earned, self.reward_initial)) if self.reward_initial else max(0.0, earned)

    @property
    def progress_pct(self) -> float:
        return 100.0 * self.progress_current / self.progress_desired if self.progress_desired else 0.0


class ProjectSnapshot(models.Model):
    """Progress and pool of a project at a moment something had changed."""

    project = models.ForeignKey(CorpProject, on_delete=models.CASCADE, related_name="snapshots")
    taken_at = models.DateTimeField(db_index=True)
    state = models.CharField(max_length=20, blank=True)
    progress_current = models.BigIntegerField(default=0)
    reward_remaining = models.FloatField(default=0)


class ProjectContribution(models.Model):
    """A contributor's total on a project at a moment it had changed."""

    project = models.ForeignKey(CorpProject, on_delete=models.CASCADE, related_name="contributions")
    taken_at = models.DateTimeField(db_index=True)
    character_id = models.BigIntegerField(db_index=True)
    character_name = models.CharField(max_length=100, blank=True)
    contributed = models.BigIntegerField(default=0)


class MaterialType(models.Model):
    """Name cache for material type IDs."""

    type_id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    volume = models.FloatField(default=0)

    def __str__(self):
        return self.name


class PriceSnapshot(models.Model):
    """Latest market aggregates for one type at one market location."""

    type_id = models.PositiveIntegerField()
    location = models.ForeignKey(MarketLocation, on_delete=models.CASCADE)
    sell_min = models.FloatField(null=True)
    sell_percentile = models.FloatField(null=True)
    sell_volume = models.FloatField(default=0, help_text="Units on sell orders")
    sell_orders = models.PositiveIntegerField(default=0)
    buy_max = models.FloatField(null=True)
    buy_max_near = models.FloatField(null=True, help_text="Highest buy order that reaches the station, incl. nearby systems in range (ESI)")
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("type_id", "location")]
        indexes = [models.Index(fields=["type_id"])]


class ShipMarketStats(models.Model):
    """Regional history aggregates for a ship."""

    ship = models.OneToOneField(Ship, on_delete=models.CASCADE, related_name="market_stats")
    region_id = models.PositiveIntegerField(default=constants.THE_FORGE_REGION_ID)
    avg_daily_volume = models.FloatField(default=0)
    avg_price = models.FloatField(default=0)
    days = models.PositiveSmallIntegerField(default=7)
    fetched_at = models.DateTimeField(default=timezone.now)


class BuildSnapshot(models.Model):
    """Bill of materials and job cost for one ship at one facility (ME 0, all skills V)."""

    ship = models.ForeignKey(Ship, on_delete=models.CASCADE, related_name="builds")
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name="builds")
    me = models.PositiveSmallIntegerField(default=0)
    materials = models.JSONField(default=list, help_text="[{type_id, quantity}]")
    estimated_item_value = models.FloatField(default=0)
    job_cost = models.FloatField(default=0, help_text="Total job cost incl. SCC and facility tax")
    system_cost_isk = models.FloatField(default=0)
    scc_surcharge = models.FloatField(default=0)
    facility_tax_isk = models.FloatField(default=0)
    time_seconds = models.PositiveIntegerField(default=0)
    materials_volume = models.FloatField(default=0)
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("ship", "facility", "me")]


class UserSettings(models.Model):
    """Per-member dashboard settings."""

    SKILLS_MANUAL = "manual"
    SKILLS_ESI = "esi"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shipyard_settings")
    facility = models.ForeignKey(Facility, null=True, blank=True, on_delete=models.SET_NULL)
    market = models.ForeignKey(MarketLocation, null=True, blank=True, on_delete=models.SET_NULL)
    use_lp_pricing = models.BooleanField(default=False, help_text="Price blueprints from LP store offers where available")

    skills_source = models.CharField(max_length=10, default=SKILLS_MANUAL)
    skills_character_id = models.PositiveIntegerField(null=True, blank=True)
    skills_character_name = models.CharField(max_length=100, blank=True)
    skills_fetched_at = models.DateTimeField(null=True, blank=True)
    standings = models.JSONField(
        default=dict, blank=True,
        help_text="Unmodified standings of the skills character, {entity id: standing}, read from ESI with the skills",
    )
    standings_fetched_at = models.DateTimeField(null=True, blank=True)
    accounting = models.PositiveSmallIntegerField(default=0)
    broker_relations = models.PositiveSmallIntegerField(default=0)
    industry = models.PositiveSmallIntegerField(default=5)
    advanced_industry = models.PositiveSmallIntegerField(default=5)
    adv_small_ship = models.PositiveSmallIntegerField(default=0)
    adv_medium_ship = models.PositiveSmallIntegerField(default=0)
    adv_large_ship = models.PositiveSmallIntegerField(default=0)
    adv_industrial_ship = models.PositiveSmallIntegerField(default=0)
    scrapmetal_processing = models.PositiveSmallIntegerField(default=0)

    # Reprocessing tab (0.10.0): the member's own levels, {skill type id: level}; missing = V.
    # Implant in percent (0, 1, 2, 4). Source tells where the levels came from.
    repro_skills = models.JSONField(default=dict, blank=True)
    repro_implant = models.PositiveSmallIntegerField(default=4)
    repro_source = models.CharField(max_length=10, default="default", help_text="default | manual | esi")
    repro_character_name = models.CharField(max_length=100, blank=True)
    repro_fetched_at = models.DateTimeField(null=True, blank=True)

    bpc_markup = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Blueprint markup for this member in % (blank = the corp's default). Managers only; 0 for people who build from their own stash.")
    manual_sales_tax = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, help_text="Override sales tax % (from the in-game market window)")
    manual_broker_fee = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, help_text="Override broker fee %")

    class Meta:
        verbose_name_plural = "user settings"

    def __str__(self):
        return f"Settings {self.user}"

    @property
    def markup_fraction(self):
        """The blueprint markup this member pays, as a fraction; None = the corp's default."""
        return float(self.bpc_markup) / 100.0 if self.bpc_markup is not None else None

    def skill_levels(self):
        return {field: getattr(self, field) for field, _, _ in constants.RELEVANT_SKILLS.values()}

    def standing_with(self, entity_id) -> float:
        """Unmodified standing with a faction or corporation; 0 when unknown."""
        if not entity_id:
            return 0.0
        return float((self.standings or {}).get(str(int(entity_id)), 0.0))


class CharacterSync(models.Model):
    """One of the member's characters that the industry page reads from ESI."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shipyard_characters")
    character_id = models.PositiveIntegerField()
    character_name = models.CharField(max_length=100)
    jobs_at = models.DateTimeField(null=True, blank=True)
    blueprints_at = models.DateTimeField(null=True, blank=True)
    assets_at = models.DateTimeField(null=True, blank=True)
    manufacturing_slots = models.PositiveSmallIntegerField(default=1)
    science_slots = models.PositiveSmallIntegerField(default=1)
    last_error = models.CharField(max_length=300, blank=True)

    class Meta:
        unique_together = [("user", "character_id")]

    def __str__(self):
        return self.character_name


class IndustryJob(models.Model):
    """An industry job of one of the member's characters, as ESI reports it."""

    job_id = models.BigIntegerField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shipyard_jobs")
    character_id = models.PositiveIntegerField()
    character_name = models.CharField(max_length=100)
    activity_id = models.PositiveSmallIntegerField(default=0)
    blueprint_type_id = models.PositiveIntegerField(default=0)
    product_type_id = models.PositiveIntegerField(null=True, blank=True)
    runs = models.PositiveIntegerField(default=0)
    licensed_runs = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    location_id = models.BigIntegerField(default=0)
    cost = models.FloatField(default=0)
    fetched_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Job {self.job_id}"


class CorpIndustryJob(models.Model):
    """An industry job of the production corp (services/business.py): copied hourly from ESI and kept,
    because ESI only serves the last 90 days. The owner's jobs run in the corp's name."""

    job_id = models.BigIntegerField(primary_key=True)
    corporation_id = models.PositiveIntegerField(db_index=True)
    installer_id = models.BigIntegerField(default=0, db_index=True)
    installer_name = models.CharField(max_length=100, blank=True)
    activity_id = models.PositiveSmallIntegerField(default=0)
    blueprint_type_id = models.PositiveIntegerField(default=0)
    product_type_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    runs = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20)
    start_date = models.DateTimeField(null=True, blank=True, db_index=True)
    end_date = models.DateTimeField(null=True, blank=True)
    completed_date = models.DateTimeField(null=True, blank=True)
    location_id = models.BigIntegerField(default=0)
    cost = models.FloatField(default=0)
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"Corp job {self.job_id}"


class CharacterBlueprint(models.Model):
    """A blueprint one of the member's characters owns."""

    item_id = models.BigIntegerField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shipyard_blueprints")
    character_id = models.PositiveIntegerField()
    type_id = models.PositiveIntegerField()
    location_id = models.BigIntegerField(default=0)
    location_flag = models.CharField(max_length=50, blank=True)
    me = models.PositiveSmallIntegerField(default=0)
    te = models.PositiveSmallIntegerField(default=0)
    runs = models.IntegerField(default=-1)
    quantity = models.IntegerField(default=-1, help_text="-1 original, -2 copy, >0 a stack of originals")
    fetched_at = models.DateTimeField(default=timezone.now)

    @property
    def is_copy(self):
        return self.quantity == -2


class CharacterAsset(models.Model):
    """Stock of one known type at one station or structure, per character."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shipyard_assets")
    character_id = models.PositiveIntegerField()
    type_id = models.PositiveIntegerField()
    location_id = models.BigIntegerField(default=0)
    quantity = models.BigIntegerField(default=0)
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("user", "character_id", "type_id", "location_id")]


class LocationName(models.Model):
    """Name cache for stations, structures and other places assets and jobs sit in."""

    location_id = models.BigIntegerField(primary_key=True)
    name = models.CharField(max_length=200)
    system_name = models.CharField(max_length=100, blank=True)
    kind = models.CharField(max_length=20, default="unknown")
    fetched_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class RefreshRun(models.Model):
    """Log of background refreshes."""

    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    step = models.CharField(max_length=40)
    ok = models.BooleanField(default=False)
    items = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]


class BooksBaseline(models.Model):
    """A reporting period of the Finance tab, with the corporation's position at its start (the opening).
    The oldest row is the owner's working budget (2026-10-18: the loan that counts as nothing); every
    State of the Alliance post after it opens a new period, created by the hourly task from the alliance
    site's posts.json (or by hand). Section 2 shows the movements since the newest period's start and adds
    up to the result minus the opening result."""

    taken_at = models.DateTimeField(help_text="The period's start (EVE time): the budget baseline, or the date of a State of the Alliance post")
    loan = models.FloatField(help_text="The working budget lent by the owner, ISK (the same on every row)")
    wallet = models.FloatField(help_text="Master wallet (division 1) at the start, ISK")
    other_divs = models.FloatField(default=0, help_text="Wallet divisions 2 to 6 at the start, ISK")
    pool = models.FloatField(help_text="Reward ISK in the active projects at the start, ISK")
    held = models.FloatField(default=0, help_text="Goods from project buybacks held at the start, at what the projects paid")
    open_escrow = models.FloatField(default=0, help_text="ISK in open buy orders at the start")
    lp_units = models.IntegerField(default=0, help_text="Loyalty points held at the start")
    lp_cost = models.FloatField(default=0, help_text="What those loyalty points cost, ISK")
    opening_result = models.FloatField(default=0, help_text="Assets above the loan at the start, ISK (0 for the budget baseline)")
    source = models.CharField(max_length=200, blank=True, help_text="What opened the period: the State of the Alliance post's title and date")
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["taken_at"]
        verbose_name = "books period"
        verbose_name_plural = "books periods"

    def __str__(self):
        return f"Baseline {self.taken_at:%Y-%m-%d %H:%M}: {self.loan / 1e6:,.0f} M"


class BookStock(models.Model):
    """A batch of stock the corporation bought to sell (Heavy Water for the Orcas): held at its buy value
    until sold, first in first out. Market buys of the same type are picked up by themselves; enter here
    what was bought by direct trade."""

    name = models.CharField(max_length=100)
    type_id = models.PositiveIntegerField()
    units = models.BigIntegerField()
    unit_cost = models.FloatField(null=True, blank=True, help_text="Buy value per unit, ISK, for a purchase. Leave empty for an LP store redemption: its cost is worked out from the LP, the input items and the ISK below")
    bought_at = models.DateTimeField(help_text="When it was bought or redeemed (EVE time)")
    lp_used = models.PositiveIntegerField(default=0, help_text="LP store redemption: LP used, valued at what the corp paid per LP")
    input_type_id = models.PositiveIntegerField(null=True, blank=True, help_text="LP store redemption: the item the offer takes in (e.g. 11289 Cap Booster 800), used from the corp's stock")
    input_units = models.BigIntegerField(default=0, help_text="LP store redemption: how many of that item")
    isk_paid = models.FloatField(default=0, help_text="LP store redemption: the ISK part of the offers")
    isk_paid_by = models.CharField(max_length=10, default="outside", choices=[("outside", "A character's own wallet (a contribution to the corp)"), ("corp", "A corporation wallet")])
    list_price = models.FloatField(null=True, blank=True, help_text="Price it is listed at, for the sheet")
    location_name = models.CharField(max_length=150, blank=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["bought_at"]
        verbose_name = "stock batch"
        verbose_name_plural = "stock batches"

    def __str__(self):
        return f"{self.name}: {self.units:,} at {self.unit_cost:g}"


class BookDirectSale(models.Model):
    """What a direct sale of project goods sold (owner, 2026-10-21), for a deposit whose reason does not
    name the items. The deposit into the corp wallet carries "direct sale" in its reason; the items are
    read from the reason after those words ("direct sale 2,388 Zero-Point Condensate, 373 Crystalline
    Isogen-10") or, when the reason says nothing useful, from this row by the journal entry id."""

    corporation_id = models.PositiveIntegerField(db_index=True)
    entry_id = models.BigIntegerField(null=True, blank=True, help_text="The journal entry of the deposit, once it appeared")
    code = models.CharField(max_length=10, blank=True, default="", db_index=True, help_text="DS-XXXX: the deposit's reason carries it")
    items = models.CharField(max_length=500, help_text="Comma-separated, a quantity before each name: '2,388 Zero-Point Condensate, 373 Crystalline Isogen-10'. An ore is converted to its minerals as the ledger does; a name without a quantity takes every unit held")
    lines = models.JSONField(default=list, blank=True, help_text="The quoted lines: type id, name, quantity, unit price, line, cost")
    quote = models.FloatField(default=0, help_text="ISK the sale was quoted at")
    cost = models.FloatField(default=0, help_text="What the projects paid for the goods, at registration")
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=150, blank=True)
    matched_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("corporation_id", "entry_id")]
        verbose_name = "direct sale"
        verbose_name_plural = "direct sales"

    @property
    def profit(self) -> float:
        return (self.quote or 0.0) - (self.cost or 0.0)

    def __str__(self):
        return f"direct sale {self.code or self.entry_id}: {self.items[:60]}"


class BookIgnoredEntry(models.Model):
    """A corporation journal line the Finance tab leaves out (owner, 2026-10-20): mistakes that will be
    corrected and net to zero, such as sales from orders put up on the corporation by accident and the
    transfers that settle them. The line still exists in EVE; the books pretend it does not. Lines whose
    reason matches SHIPYARD_BOOKS_IGNORE_REASONS are left out without a row here."""

    corporation_id = models.PositiveIntegerField(db_index=True)
    division = models.PositiveSmallIntegerField()
    entry_id = models.BigIntegerField()
    reason = models.CharField(max_length=200, blank=True, help_text="Why the line is left out")
    amount = models.FloatField(null=True, blank=True, help_text="ISK of the line to leave out, as a positive number; empty = the whole line. The rest stays in the books (a deposit that settles a mistake and brings some real money as well)")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("corporation_id", "division", "entry_id")]
        verbose_name = "ignored journal line"
        verbose_name_plural = "ignored journal lines"

    def __str__(self):
        return f"ignore {self.entry_id} ({self.reason})"


class LpSnapshot(models.Model):
    """The LP log (owner, 2026-10-22): a reading of one character's loyalty points with one NPC corporation.

    The hourly task reads every character's balances (ESI, cached an hour) and keeps a row only when a
    balance changed since the previous reading, so the rows are the log: when, who, which corporation,
    by how much. The first reading of a character stores every balance with change 0."""

    character_id = models.PositiveIntegerField(db_index=True)
    character_name = models.CharField(max_length=100, blank=True)
    corporation_id = models.PositiveIntegerField(db_index=True)
    corporation_name = models.CharField(max_length=100, blank=True)
    loyalty_points = models.BigIntegerField(help_text="The balance at this reading")
    change = models.BigIntegerField(default=0, help_text="Against the previous reading; 0 on the first reading")
    previous_at = models.DateTimeField(null=True, blank=True, help_text="When the previous reading of this pair was taken")
    is_first = models.BooleanField(default=False)
    taken_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-taken_at"]
        indexes = [models.Index(fields=["character_id", "corporation_id", "taken_at"])]
        verbose_name = "LP log reading"
        verbose_name_plural = "LP log readings"

    def __str__(self):
        return f"{self.character_name} {self.corporation_name} {self.change:+} -> {self.loyalty_points} at {self.taken_at:%Y-%m-%d %H:%M}"


class HangarItem(models.Model):
    """The corporation's hangars as EVE shows them (owner's rule, 2026-10-23): the goods held from project buybacks
    are what is physically in the projects hangar, nothing else. One row per item type, office and hangar division
    at the last read (hourly task, ESI corporation assets); every read replaces the rows."""

    corporation_id = models.PositiveIntegerField(db_index=True)
    type_id = models.PositiveIntegerField(db_index=True)
    name = models.CharField(max_length=100, blank=True)
    quantity = models.BigIntegerField(default=0)
    location_id = models.BigIntegerField(help_text="The office's station or structure")
    location_flag = models.CharField(max_length=40, help_text="CorpSAG1 to CorpSAG7 (hangar divisions 1 to 7) or CorpDeliveries")
    read_at = models.DateTimeField()

    class Meta:
        verbose_name = "hangar item"
        verbose_name_plural = "hangar items (last read)"

    def __str__(self):
        return f"{self.quantity:,} {self.name or self.type_id} in {self.location_flag} at {self.location_id}"


class MarketHistoryDay(models.Model):
    """One day of EVE Ref's market-history archive, The Forge rows only, compressed (the Bargains tab, 0.29.0)."""

    day = models.DateField(primary_key=True)
    total = models.PositiveIntegerField(help_text="Records for the day in EVE Ref's totals.json when fetched; a change means the archive was completed and is fetched again")
    rows = models.PositiveIntegerField(default=0)
    data = models.BinaryField(help_text="zlib-compressed lines: type_id,average,lowest,highest,volume,order_count (The Forge only)")
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "market history day"
        verbose_name_plural = "market history days (The Forge)"

    def __str__(self):
        return f"{self.day}: {self.rows:,} types"


class MarketTypeStat(models.Model):
    """Every type traded in The Forge against its own year (the Bargains tab, 0.29.0)."""

    type_id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=100, blank=True)
    market_group_id = models.PositiveIntegerField(null=True, blank=True)
    group_path = models.CharField(max_length=300, blank=True)
    top_group = models.CharField(max_length=100, blank=True, db_index=True)
    as_of = models.DateField(null=True, blank=True)
    last_date = models.DateField(null=True, blank=True)
    last_avg = models.FloatField(null=True, blank=True)
    last_low = models.FloatField(null=True, blank=True)
    low52 = models.FloatField(null=True, blank=True)
    low52_date = models.DateField(null=True, blank=True)
    high52 = models.FloatField(null=True, blank=True)
    high52_date = models.DateField(null=True, blank=True)
    avg30 = models.FloatField(null=True, blank=True)
    avg90 = models.FloatField(null=True, blank=True)
    avg365 = models.FloatField(null=True, blank=True)
    days365 = models.PositiveIntegerField(default=0)
    vol30 = models.FloatField(default=0)
    isk30 = models.FloatField(default=0, db_index=True)
    sell_min = models.FloatField(null=True, blank=True)
    buy_max = models.FloatField(null=True, blank=True)
    sell_volume = models.FloatField(default=0)
    sell_orders = models.PositiveIntegerField(default=0)
    prices_at = models.DateTimeField(null=True, blank=True)
    pos52 = models.FloatField(null=True, blank=True)
    vs90 = models.FloatField(null=True, blank=True)
    vs365 = models.FloatField(null=True, blank=True)
    flag_low = models.BooleanField(default=False, db_index=True)
    flag_dip = models.BooleanField(default=False, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "market type statistics"
        verbose_name_plural = "market type statistics (bargains)"

    def __str__(self):
        return f"{self.name or self.type_id}: low {self.low52} high {self.high52}"
