from django.urls import path

from . import views

app_name = "app"
urlpatterns = [
    path("", views.home, name="home"),
    path("cursos", views.cursos, name="cursos"),
    path("tutoriais", views.tutoriais, name="tutoriais"),
    path("comunidade", views.comunidade, name="comunidade"),
    path("meuperfil", views.meuperfil, name="meuperfil"),
]
