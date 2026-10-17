from django.urls import path

from . import views

app_name = "doctrines"

urlpatterns = [
    path("", views.index, name="index"),
    path("go/", views.go, name="go"),
    path("ship/<int:pk>/fit.txt", views.fit_text, name="fit_text"),
    path("character/<int:character_id>/use/", views.use_character, name="use_character"),
    path("character/refresh/", views.character_refresh, name="character_refresh"),
    path("<slug:slug>/", views.doctrine, name="doctrine"),
]
