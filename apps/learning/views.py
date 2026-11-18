"""
This module (views.py) corresponds to the 'Controller' in the MVC Architecture.

The MVC 'View' is the 'templates/' folder
"""

from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import TemplateView

from . import nasa_images
from .forms import SpaceImageSearchForm


class HomeView(TemplateView):
    template_name = "learning/home.html"


class CursosView(TemplateView):
    template_name = "learning/cursos.html"


class TutoriaisView(TemplateView):
    template_name = "learning/tutoriais.html"


class ComunidadeView(TemplateView):
    template_name = "learning/comunidade.html"


class MeuPerfilView(LoginRequiredMixin, TemplateView):
    template_name = "learning/meuperfil.html"


class AcessibilidadeView(TemplateView):
    template_name = "learning/acessibilidade.html"


# a NASA descreve as imagens em ingles: cada atalho tem o nome em portugues e a pesquisa em ingles
SPACE_TOPICS = (
    ("Nebulosas", "nebula"),
    ("Galáxias", "galaxy"),
    ("Aglomerados de estrelas", "star cluster"),
    ("Buracos negros", "black hole"),
    ("Sol", "sun"),
    ("Crateras da Lua", "moon crater"),
    ("Superfície de Marte", "mars surface"),
    ("Júpiter", "jupiter"),
    ("Saturno", "saturn"),
    ("Cometas", "comet"),
    ("Auroras", "aurora"),
)


def search_params(form, page=1):
    """Parametros de uma pesquisa valida, para os links de paginas e o de voltar aos resultados."""
    params = {name: value for name, value in form.cleaned_data.items() if value}
    if page > 1:
        params["pagina"] = page
    return urlencode(params)


def page_number(value):
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 1
    return min(max(page, 1), nasa_images.MAX_PAGE)


class SpaceImagesMixin:
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context, status=context.get("status", 200))


class AstronomiaView(SpaceImagesMixin, TemplateView):
    template_name = "learning/astronomia.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = SpaceImageSearchForm(self.request.GET or None)
        context.update(form=form, topics=SPACE_TOPICS)
        if not form.is_valid():
            # depois de pesquisar, o foco vai para o primeiro campo a corrigir
            for name in form.errors:
                form.fields[name].widget.attrs["autofocus"] = True
                break
            return context

        page = page_number(self.request.GET.get("pagina"))
        try:
            results = nasa_images.search(
                form.cleaned_data["q"],
                year_start=form.cleaned_data["ano_inicio"],
                year_end=form.cleaned_data["ano_fim"],
                page=page,
            )
        except nasa_images.NasaImagesError as error:
            context.update(error=str(error), status=502)
            return context

        base = reverse("learning:astronomia")
        context.update(
            results=results,
            # cada imagem leva a pesquisa junto, para o link de voltar aos resultados
            search_query=search_params(form, page),
            # depois da ultima pagina, a anterior e a ultima que tem imagens
            prev_url=f"{base}?{search_params(form, min(page - 1, results.pages))}"
            if page > 1
            else None,
            next_url=f"{base}?{search_params(form, page + 1)}"
            if page < results.pages
            else None,
            last_url=f"{base}?{search_params(form, results.pages)}",
        )
        return context


class AstronomiaImagemView(SpaceImagesMixin, TemplateView):
    template_name = "learning/astronomia_imagem.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        back_url = reverse("learning:astronomia")
        form = SpaceImageSearchForm(self.request.GET)
        if form.is_valid():
            page = page_number(self.request.GET.get("pagina"))
            context["back_to_results"] = True
            back_url += "?" + search_params(form, page)
        context["back_url"] = back_url

        try:
            image = nasa_images.get_image(kwargs["nasa_id"])
        except nasa_images.NasaImagesError as error:
            context.update(error=str(error), status=502)
            return context
        if image is None:
            context["status"] = 404
            return context

        context["image"] = image
        return context
