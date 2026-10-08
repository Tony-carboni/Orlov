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
            ("manage_shipyard", "Can edit blueprint prices, LP prices and facilities"),
            ("view_corp_industry", "Can see the industry of everyone in their corporation"),
            ("view_alliance_industry", "Can see the industry of everyone in the alliance"),
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
