from django.urls import path

from . import views

app_name = "doctrines"

urlpatterns = [
    path("", views.index, name="index"),
    path("go/", views.go, name="go"),
    path("ship/<int:pk>/fit.txt", views.fit_text, name="fit_text"),
    path("<slug:slug>/", views.doctrine, name="doctrine"),
]
