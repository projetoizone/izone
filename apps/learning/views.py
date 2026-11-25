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
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET
from . import nasa_images, wikipedia
from .forms import SpaceImageSearchForm, WikipediaSearchForm


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


def page_number(value, last):
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 1
    return min(max(page, 1), last)


class StatusFromContextMixin:
    """Responde com o status que o contexto pede: 404 se nao achou, 502 se a API falhou."""

    def get(self, request, *args, **kwargs):
        return self.render_context(self.get_context_data(**kwargs))

    def render_context(self, context):
        return self.render_to_response(context, status=context.get("status", 200))


def page_links(url_name, form, page, pages):
    """Os links entre as paginas de uma pesquisa, que levam a pesquisa junto."""
    base = reverse(url_name)
    return {
        # cada resultado leva a pesquisa junto, para o link de voltar aos resultados
        "search_query": search_params(form, page),
        # depois da ultima pagina, a anterior e a ultima que tem resultados
        "prev_url": f"{base}?{search_params(form, min(page - 1, pages))}"
        if page > 1
        else None,
        "next_url": f"{base}?{search_params(form, page + 1)}" if page < pages else None,
        "last_url": f"{base}?{search_params(form, pages)}",
    }


def back_link(request, form_class, url_name, last_page):
    """O link de voltar: aos resultados, se a pagina veio de uma pesquisa, ou a pesquisa vazia."""
    url = reverse(url_name)
    form = form_class(request.GET)
    if not form.is_valid():
        return {"back_url": url}
    page = page_number(request.GET.get("pagina"), last_page)
    return {"back_url": f"{url}?{search_params(form, page)}", "back_to_results": True}


class AstronomiaView(StatusFromContextMixin, TemplateView):
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

        page = page_number(self.request.GET.get("pagina"), nasa_images.MAX_PAGE)
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

        context["results"] = results
        context.update(page_links("learning:astronomia", form, page, results.pages))
        return context


class AstronomiaImagemView(StatusFromContextMixin, TemplateView):
    template_name = "learning/astronomia_imagem.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            back_link(
                self.request,
                SpaceImageSearchForm,
                "learning:astronomia",
                nasa_images.MAX_PAGE,
            )
        )
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


class WikipediaView(StatusFromContextMixin, TemplateView):
    template_name = "learning/wikipedia.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = WikipediaSearchForm(self.request.GET or None)
        context["form"] = form
        if not form.is_valid():
            # depois de pesquisar, o foco vai para o campo a corrigir
            if form.errors:
                form.fields["q"].widget.attrs["autofocus"] = True
            return context

        page = page_number(self.request.GET.get("pagina"), wikipedia.MAX_PAGE)
        try:
            results = wikipedia.search(form.cleaned_data["q"], page=page)
        except wikipedia.WikipediaError as error:
            context.update(error=str(error), status=502)
            return context

        context["results"] = results
        context["suggestion_url"] = (
            f"{reverse('learning:wikipedia')}?{urlencode({'q': results.suggestion})}"
        )
        context.update(page_links("learning:wikipedia", form, page, results.pages))
        return context


class WikipediaArtigoView(StatusFromContextMixin, TemplateView):
    template_name = "learning/wikipedia_artigo.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        article = context.get("article")
        # outros nomes do artigo (redirecionamentos, minusculas, espacos) levam ao endereco dele
        if article and article.slug != kwargs["titulo"]:
            url = reverse("learning:wikipedia_artigo", args=[article.slug])
            if request.GET:
                url += "?" + request.GET.urlencode()
            return redirect(url)
        return self.render_context(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            back_link(
                self.request,
                WikipediaSearchForm,
                "learning:wikipedia",
                wikipedia.MAX_PAGE,
            )
        )
        try:
            article = wikipedia.get_article(kwargs["titulo"].replace("_", " "))
        except wikipedia.WikipediaError as error:
            context.update(error=str(error), status=502)
            return context
        if article is None:
            context["status"] = 404
            return context

        context["article"] = article
        return context
