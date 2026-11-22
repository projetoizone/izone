"""
This module (views.py) corresponds to the 'Controller' in the MVC Architecture.

The MVC 'View' is the 'templates/' folder
"""

from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import TemplateView

from urllib.parse import quote

import requests
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
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


class DicionarioView(TemplateView):
    template_name = "learning/dictionary.html"


@require_GET
def get_definition(request):
    """Consulta a Free Dictionary API e retorna a primeira definição encontrada."""
    word = request.GET.get("word", "").strip()

    if not word:
        return JsonResponse({"error": "Digite uma palavra para pesquisar."}, status=400)

    # Codifica a palavra para que espaços e caracteres especiais não quebrem a URL.
    encoded_word = quote(word, safe="")
    api_url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{encoded_word}"

    try:
        response = requests.get(api_url, timeout=10)

        if response.status_code == 404:
            return JsonResponse({"error": "Palavra não encontrada."}, status=404)

        response.raise_for_status()
        data = response.json()

        entry = data[0]

        phonetics = [
            {
                "text": item.get("text"),
                "audio": item.get("audio"),
            }
            for item in entry.get("phonetics", [])
            if item.get("text") or item.get("audio")
        ]

        meanings = []

        for meaning in entry.get("meanings", []):
            definitions = []

            for item in meaning.get("definitions", []):
                definitions.append({
                    "definition": item.get("definition"),
                    "example": item.get("example"),
                    "synonyms": item.get("synonyms", []),
                    "antonyms": item.get("antonyms", []),
                })

            meanings.append({
                "part_of_speech": meaning.get("partOfSpeech"),
                "definitions": definitions,
                "synonyms": meaning.get("synonyms", []),
                "antonyms": meaning.get("antonyms", []),
            })


        return JsonResponse({
            "word": entry.get("word", word),
            "phonetics": phonetics,
            "meanings": meanings,
            "license": entry.get("license"),
            "source_urls": entry.get("sourceUrls", []),
        })

    except requests.Timeout:
        return JsonResponse(
            {"error": "A consulta ao dicionário demorou demais. Tente novamente."},
            status=504,
        )
    except requests.RequestException:
        return JsonResponse(
            {"error": "Não foi possível acessar o serviço de dicionário."},
            status=502,
        )
    except (ValueError, IndexError, KeyError, TypeError):
        return JsonResponse(
            {"error": "O serviço retornou uma resposta em formato inesperado."},
            status=502,
        )
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
