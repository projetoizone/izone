from django.urls import path

from . import views

app_name = "spelling"
urlpatterns = [
    path("game", views.GameView.as_view(), name="game"),
]
