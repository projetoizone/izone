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
    path("cursos/wikipedia", views.WikipediaView.as_view(), name="wikipedia"),
    path(
        "cursos/wikipedia/<path:titulo>",
        views.WikipediaArtigoView.as_view(),
        name="wikipedia_artigo",
    ),
    path("tutoriais", views.TutoriaisView.as_view(), name="tutoriais"),
    path("comunidade", views.ComunidadeView.as_view(), name="comunidade"),
    path("meuperfil", views.MeuPerfilView.as_view(), name="meuperfil"),

    # Dicionário
    path("cursos/dictionary", views.DicionarioView.as_view(), name="dictionary"),
    path("api/definition", views.get_definition, name="get_definition"),
    path("acessibilidade", views.AcessibilidadeView.as_view(), name="acessibilidade"),
]
