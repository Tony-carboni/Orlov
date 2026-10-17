"""Doctrines: categories, doctrines, the ships in them with their fittings, and the price and
insurance caches the pages read from. Edited in auth's admin by members with manage_doctrines."""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class General(models.Model):
    """Permission holder only (no table)."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = (
            ("basic_access", "Can read the fleet doctrines"),
            ("manage_doctrines", "Can edit doctrines, ships and fittings"),
        )


class SiteText(models.Model):
    """The landing page's text: the general philosophy that funnels readers to the doctrines. One row."""

    title = models.CharField(max_length=120, default="How we fly")
    body = models.TextField(blank=True, help_text="Plain text. A blank line starts a new paragraph; a line starting with '- ' is a bullet.")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "landing page text"
        verbose_name_plural = "landing page text"

    def __str__(self):
        return self.title


class Category(models.Model):
    """A row of tiles on the landing page: Light & cheap, Bread and butter, Support, APEX."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    blurb = models.CharField(max_length=300, blank=True, help_text="One line under the category name")

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:60]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SrpLevel(models.Model):
    """An SRP (ship replacement) level a ship can carry, for example Full, Partial, Logi only, None."""

    name = models.CharField(max_length=40, unique=True)
    order = models.PositiveSmallIntegerField(default=0)
    description = models.CharField(max_length=200, blank=True, help_text="Shown on hover, e.g. 'hull and fit replaced in full'")
    colour = models.CharField(max_length=20, default="secondary", help_text="Bootstrap colour name for the badge: success, warning, danger, info, secondary")

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "SRP level"
        verbose_name_plural = "SRP levels"

    def __str__(self):
        return self.name


class Doctrine(models.Model):
    """One fleet doctrine: a tile on the landing page and its own page."""

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="doctrines")
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    gameplay = models.CharField(max_length=60, help_text="What it is for, shown on the tile: Home defense, Faction warfare, Wormhole, Nullsec roam, ...")
    summary = models.CharField(max_length=300, blank=True, help_text="One or two lines on the tile")
    tile_type_id = models.PositiveIntegerField(null=True, blank=True, help_text="EVE type id of the ship pictured on the tile; blank = the first ship of the doctrine")
    description = models.TextField(blank=True, help_text="What the fleet is and how it fights. Plain text: blank line = new paragraph, '- ' = bullet.")
    pros = models.TextField(blank=True, help_text="One per line")
    cons = models.TextField(blank=True, help_text="One per line")
    strategy = models.TextField(blank=True, help_text="Strategy notes: engagement, ranges, logistics, retreat. Plain text as above.")
    composition = models.TextField(blank=True, help_text="Target ratio of the roles, one per line as 'Role: number', e.g. 'DPS: 5', 'Logistics: 3', 'Tackle: 1', 'Support: 1'. Shown on the card.")
    srp_percent = models.PositiveSmallIntegerField(default=0, help_text="Ship replacement paid on a loss, as a percentage of the ship's cost (hull, fit, drones, cargo). Shown as a tag on the page and taken off the 'loss if lost' column. 0 = no SRP tag")
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, help_text="Unticked: hidden from members, still editable")
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["category__order", "order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:80]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def picture_type_id(self):
        if self.tile_type_id:
            return self.tile_type_id
        first = self.ships.filter(is_active=True).order_by("order", "id").first()
        return first.ship_type_id if first else None


class DoctrineShip(models.Model):
    """A ship in a doctrine with its fitting. The fitting is pasted from the game (EFT format);
    on save it is parsed and every item resolved to an EVE type, so the page can draw the slots,
    price it and insure it without talking to EVE again."""

    doctrine = models.ForeignKey(Doctrine, on_delete=models.CASCADE, related_name="ships")
    order = models.PositiveSmallIntegerField(default=0)
    name = models.CharField(max_length=100, help_text="The fit's name, e.g. 'Harpy, Rail Harpy v3'")
    role = models.CharField(max_length=60, help_text="Role in the fleet: DPS, Logistics, Tackle, EWAR, Boosts, Scout, FC, ...")
    variant = models.CharField(max_length=12, blank=True, help_text="T1, T2, ... when the same hull and role has several fits (lower-skill and full-skill versions); the page lists the hull once and shows the variants on click. Blank = the only fit")
    srp_level = models.ForeignKey(SrpLevel, on_delete=models.SET_NULL, null=True, blank=True, related_name="ships")
    srp_percent = models.PositiveSmallIntegerField(null=True, blank=True, help_text="SRP for this ship as a percentage of its cost; blank = the doctrine's percentage (e.g. 100 for logistics in a 50 % doctrine)")
    notes = models.CharField(max_length=300, blank=True, help_text="Short line under the ship: skills, implants, how many wanted")
    fitting_text = models.TextField(help_text="Paste the fitting as the game exports it: fitting window → Export → To clipboard (EFT format). First line [Hull, Fit name], then the modules, one per line, drones as 'Hobgoblin II x5'.")
    ship_type_id = models.PositiveIntegerField(default=0, editable=False)
    ship_type_name = models.CharField(max_length=100, blank=True, editable=False)
    fitting_json = models.JSONField(default=dict, blank=True, editable=False, help_text="The parsed fitting: slots with type ids and quantities")
    parse_error = models.CharField(max_length=300, blank=True, editable=False)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["doctrine", "order", "id"]

    def __str__(self):
        return f"{self.doctrine.name}: {self.name}"


class ItemType(models.Model):
    """What we know about an EVE type that appears in a fitting: name, group, slot."""

    type_id = models.PositiveIntegerField(primary_key=True)
    name = models.CharField(max_length=100, db_index=True)
    group_id = models.PositiveIntegerField(default=0)
    category_id = models.PositiveIntegerField(default=0)
    slot = models.CharField(max_length=12, blank=True, help_text="high, mid, low, rig, subsystem, drone, charge, implant, ship, cargo")
    volume = models.FloatField(default=0)
    fetched_at = models.DateTimeField(default=timezone.now)
    required_skills = models.JSONField(default=list, blank=True, help_text="[[skill type id, level], ...] straight from the type's dogma attributes")
    skills_fetched_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class MemberCharacter(models.Model):
    """The character a member runs the skills check with: its skills as ESI last reported them."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doctrines_character")
    character_id = models.PositiveIntegerField()
    character_name = models.CharField(max_length=100)
    skills = models.JSONField(default=dict, blank=True, help_text="{skill type id: active level} from ESI")
    total_sp = models.BigIntegerField(default=0)
    fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "member's character"
        verbose_name_plural = "members' characters"

    def __str__(self):
        return f"{self.user}: {self.character_name}"


class TypePrice(models.Model):
    """Lowest sell and highest buy at the configured market, refreshed hourly for every type in a fitting."""

    type_id = models.PositiveIntegerField(primary_key=True)
    sell_min = models.FloatField(null=True, blank=True)
    buy_max = models.FloatField(null=True, blank=True)
    updated_at = models.DateTimeField(default=timezone.now)


class Insurance(models.Model):
    """EVE's insurance table for a hull at one level (Platinum): premium and payout."""

    type_id = models.PositiveIntegerField(primary_key=True)
    level = models.CharField(max_length=20, default="Platinum")
    cost = models.FloatField(default=0)
    payout = models.FloatField(default=0)
    updated_at = models.DateTimeField(default=timezone.now)

    @property
    def net(self) -> float:
        return self.payout - self.cost


class RefreshRun(models.Model):
    """Log of the background refreshes (prices, insurance)."""

    step = models.CharField(max_length=30)
    started_at = models.DateTimeField(default=timezone.now)
    ok = models.BooleanField(default=False)
    items = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-started_at"]
