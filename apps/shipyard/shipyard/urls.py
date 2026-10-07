from django.urls import path

from . import views

app_name = "shipyard"

urlpatterns = [
    path("", views.index, name="index"),
    path("ship/<int:type_id>/", views.ship_detail, name="ship_detail"),
    path("api/sim/<int:type_id>/", views.api_simulate, name="api_simulate"),
    path("settings/", views.settings_view, name="settings"),
    path("settings/load-skills/", views.load_skills, name="load_skills"),
    path("blueprints/", views.blueprints, name="blueprints"),
]
