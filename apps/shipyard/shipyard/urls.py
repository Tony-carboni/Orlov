from django.urls import path

from . import views

app_name = "shipyard"

urlpatterns = [
    path("", views.index, name="index"),
    path("ship/<int:type_id>/", views.ship_detail, name="ship_detail"),
    path("api/sim/<int:type_id>/", views.api_simulate, name="api_simulate"),
    path("industry/", views.industry_view, name="industry"),
    path("reprocessing/", views.reprocessing_view, name="reprocessing"),
    path("scrapmetal/", views.scrapmetal_view, name="scrapmetal"),
    path("settings/", views.settings_view, name="settings"),
    path("facility/<int:pk>/use/", views.set_facility, name="set_facility"),
    path("ship/<int:type_id>/price/", views.set_bpc_price, name="set_bpc_price"),
    path("refresh/", views.refresh_now, name="refresh_now"),
    path("character/<int:character_id>/use/", views.use_character, name="use_character"),
    path("go/", views.go, name="go"),
    path("blueprints/", views.blueprints, name="blueprints"),
]
