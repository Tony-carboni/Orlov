"""Auth's admin is where doctrines are edited: categories, SRP levels, the landing text, doctrines
with their ships inline. A fitting is parsed on save; a problem shows in the 'parse error' column."""

from django import forms
from django.contrib import admin

from .models import Category, Doctrine, DoctrineShip, Insurance, ItemType, MemberCharacter, RefreshRun, SiteText, SrpLevel, TypePrice
from .services import fittings


@admin.register(SiteText)
class SiteTextAdmin(admin.ModelAdmin):
    list_display = ("title", "updated_at")

    def has_add_permission(self, request):
        return not SiteText.objects.exists()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("order", "name", "slug", "blurb")
    list_display_links = ("name",)
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(SrpLevel)
class SrpLevelAdmin(admin.ModelAdmin):
    list_display = ("order", "name", "colour", "description")
    list_display_links = ("name",)
    list_editable = ("order",)


class DoctrineShipForm(forms.ModelForm):
    class Meta:
        model = DoctrineShip
        fields = "__all__"
        widgets = {"fitting_text": forms.Textarea(attrs={"rows": 14, "cols": 60, "style": "font-family: monospace"})}


class DoctrineShipInline(admin.StackedInline):
    model = DoctrineShip
    form = DoctrineShipForm
    extra = 1
    fields = ("order", "name", "role", "variant", "srp_percent", "srp_level", "notes", "fitting_text", "is_active", "ship_type_name", "parse_error")
    readonly_fields = ("ship_type_name", "parse_error")
    ordering = ("order", "id")


@admin.register(Doctrine)
class DoctrineAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "gameplay", "srp_percent", "ship_count", "is_active", "order", "updated_at", "updated_by")
    list_filter = ("category", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("name", "gameplay", "summary")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [DoctrineShipInline]
    fieldsets = (
        (None, {"fields": ("category", "name", "slug", "gameplay", "summary", "composition", "srp_percent", "tile_type_id", "order", "is_active")}),
        ("The page", {"fields": ("description", "pros", "cons", "strategy")}),
    )

    @admin.display(description="ships")
    def ship_count(self, obj):
        return obj.ships.filter(is_active=True).count()

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user.username
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for ship in instances:
            if isinstance(ship, DoctrineShip):
                fittings.store(ship)
            ship.save()
        formset.save_m2m()
        # price the new types right away so the page does not wait for the hourly task
        try:
            from .services import prices
            ids = set()
            for ship in form.instance.ships.all():
                ids |= fittings.type_ids_of(ship)
            known = set(TypePrice.objects.filter(type_id__in=ids).values_list("type_id", flat=True))
            if ids - known:
                prices.refresh(ids - known)
        except Exception:  # noqa: BLE001
            pass


@admin.register(DoctrineShip)
class DoctrineShipAdmin(admin.ModelAdmin):
    form = DoctrineShipForm
    list_display = ("name", "doctrine", "role", "variant", "srp_percent", "srp_level", "ship_type_name", "is_active", "parse_error")
    list_filter = ("doctrine", "srp_level", "is_active")
    search_fields = ("name", "ship_type_name", "role")
    readonly_fields = ("ship_type_name", "parse_error")

    def save_model(self, request, obj, form, change):
        fittings.store(obj)
        super().save_model(request, obj, form, change)


@admin.register(ItemType)
class ItemTypeAdmin(admin.ModelAdmin):
    list_display = ("type_id", "name", "slot", "category_id", "group_id", "fetched_at")
    search_fields = ("name",)
    list_filter = ("slot",)


@admin.register(TypePrice)
class TypePriceAdmin(admin.ModelAdmin):
    list_display = ("type_id", "sell_min", "buy_max", "updated_at")


@admin.register(Insurance)
class InsuranceAdmin(admin.ModelAdmin):
    list_display = ("type_id", "level", "cost", "payout", "updated_at")


@admin.register(RefreshRun)
class RefreshRunAdmin(admin.ModelAdmin):
    list_display = ("started_at", "step", "ok", "items", "message")
    list_filter = ("step", "ok")


@admin.register(MemberCharacter)
class MemberCharacterAdmin(admin.ModelAdmin):
    """Which character each member runs the skills check with; the skills themselves come from ESI."""

    list_display = ("user", "character_name", "character_id", "total_sp", "fetched_at")
    search_fields = ("user__username", "character_name")
    readonly_fields = ("skills", "total_sp", "fetched_at")
