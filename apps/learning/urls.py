from django.urls import path

from . import views

app_name = "learning"
urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("cursos", views.CursosView.as_view(), name="cursos"),
    path("cursos/astronomia", views.AstronomiaView.as_view(), name="astronomia"),
    path(
        "cursos/astronomia/<str:nasa_id>",
        views.AstronomiaImagemView.as_view(),
        name="astronomia_imagem",
    ),
    path("tutoriais", views.TutoriaisView.as_view(), name="tutoriais"),
    path("comunidade", views.ComunidadeView.as_view(), name="comunidade"),
    path("meuperfil", views.MeuPerfilView.as_view(), name="meuperfil"),
    path("acessibilidade", views.AcessibilidadeView.as_view(), name="acessibilidade"),
]
