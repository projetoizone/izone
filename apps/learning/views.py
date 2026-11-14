"""
This module (views.py) corresponds to the 'Controller' in the MVC Architecture.

The MVC 'View' is the 'templates/' folder
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from urllib.parse import quote

import requests
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


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
