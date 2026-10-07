from django.contrib import admin

from .models import (
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
