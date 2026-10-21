from django.contrib import admin

from .models import BookDirectSale, BookIgnoredEntry, BooksBaseline, BookStock
from .models import (
    ScrapItem,
    BuildSnapshot, CharacterSync, Facility, IndustryJob, LocationName, LpFaction, MarketLocation, RefreshRun,
    Ship, ShipConfig, ShipMarketStats, UserSettings,
)


@admin.register(CharacterSync)
class CharacterSyncAdmin(admin.ModelAdmin):
    list_display = ("character_name", "user", "jobs_at", "blueprints_at", "assets_at", "manufacturing_slots", "science_slots", "last_error")


@admin.register(IndustryJob)
class IndustryJobAdmin(admin.ModelAdmin):
    list_display = ("job_id", "character_name", "activity_id", "product_type_id", "runs", "status", "end_date")
    list_filter = ("status", "activity_id")


@admin.register(LocationName)
class LocationNameAdmin(admin.ModelAdmin):
    list_display = ("location_id", "name", "system_name", "kind", "fetched_at")
    search_fields = ("name",)


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("name", "structure_name", "system_name", "facility_tax", "manufacturing_index", "is_default", "is_active")
    list_editable = ("is_default", "is_active")


@admin.register(MarketLocation)
class MarketLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "station_id", "region_id", "is_npc_station", "sales_tax_base", "broker_fee_base", "is_default", "is_active")
    list_editable = ("is_default", "is_active")


@admin.register(LpFaction)
class LpFactionAdmin(admin.ModelAdmin):
    list_display = ("name", "isk_per_lp", "notes")
    list_editable = ("isk_per_lp",)


class ShipConfigInline(admin.StackedInline):
    model = ShipConfig
    extra = 0


@admin.register(Ship)
class ShipAdmin(admin.ModelAdmin):
    list_display = ("name", "type_id", "category", "hull_size", "faction_name", "meta_group_id", "is_active")
    list_filter = ("category", "hull_size", "is_active")
    list_editable = ("is_active",)
    search_fields = ("name",)
    inlines = [ShipConfigInline]


@admin.register(BuildSnapshot)
class BuildSnapshotAdmin(admin.ModelAdmin):
    list_display = ("ship", "facility", "me", "job_cost", "estimated_item_value", "time_seconds", "fetched_at")
    list_filter = ("facility",)
    search_fields = ("ship__name",)


@admin.register(ShipMarketStats)
class ShipMarketStatsAdmin(admin.ModelAdmin):
    list_display = ("ship", "avg_daily_volume", "avg_price", "fetched_at")
    search_fields = ("ship__name",)


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "facility", "market", "use_lp_pricing", "skills_source", "skills_character_name")


@admin.register(RefreshRun)
class RefreshRunAdmin(admin.ModelAdmin):
    list_display = ("started_at", "finished_at", "step", "ok", "items", "message")
    list_filter = ("step", "ok")


@admin.register(ScrapItem)
class ScrapItemAdmin(admin.ModelAdmin):
    """Modules of the Scrapmetal tab. Add a row with the type id and a group; the weekly catalog task fills the rest."""

    list_display = ("name", "type_id", "group", "group_order", "variant", "meta_level", "volume", "is_active", "updated_at")
    list_filter = ("group", "variant", "is_active")
    list_editable = ("group", "group_order", "is_active")
    search_fields = ("name",)



@admin.register(BooksBaseline)
class BooksBaselineAdmin(admin.ModelAdmin):
    list_display = ("taken_at", "source", "loan", "wallet", "other_divs", "pool", "held", "open_escrow", "lp_units", "opening_result", "note")


@admin.register(BookDirectSale)
class BookDirectSaleAdmin(admin.ModelAdmin):
    list_display = ("entry_id", "corporation_id", "items", "note", "added_at")
    search_fields = ("entry_id", "items", "note")


@admin.register(BookIgnoredEntry)
class BookIgnoredEntryAdmin(admin.ModelAdmin):
    list_display = ("entry_id", "division", "corporation_id", "reason", "added_at")
    search_fields = ("entry_id", "reason")


@admin.register(BookStock)
class BookStockAdmin(admin.ModelAdmin):
    list_display = ("name", "type_id", "units", "unit_cost", "bought_at", "lp_used", "input_type_id", "input_units", "isk_paid", "isk_paid_by", "list_price")
