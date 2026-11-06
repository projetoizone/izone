from django.urls import path

from . import views

app_name = "learning"
urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("cursos", views.CursosView.as_view(), name="cursos"),
    path("tutoriais", views.TutoriaisView.as_view(), name="tutoriais"),
    path("comunidade", views.ComunidadeView.as_view(), name="comunidade"),
    path("meuperfil", views.MeuPerfilView.as_view(), name="meuperfil"),
]
