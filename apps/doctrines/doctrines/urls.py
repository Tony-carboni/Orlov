from django.urls import path

from . import views

app_name = "doctrines"

urlpatterns = [
    path("", views.index, name="index"),
    path("go/", views.go, name="go"),
    path("ship/<int:pk>/fit.txt", views.fit_text, name="fit_text"),
    path("character/<int:character_id>/use/", views.use_character, name="use_character"),
    path("character/refresh/", views.character_refresh, name="character_refresh"),
    path("srp/", views.srp, name="srp"),
    path("srp/add/", views.srp_add, name="srp_add"),
    path("srp/sync/", views.srp_sync, name="srp_sync"),
    path("srp/<int:pk>/", views.srp_action, name="srp_action"),
    path("<slug:slug>/", views.doctrine, name="doctrine"),
]
