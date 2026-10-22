"""
This module (views.py) corresponds to the 'Controller' in the MVC Architecture.

The MVC 'View' is the 'templates/' folder
"""

from django.shortcuts import render
from django.http import HttpResponse


def home(request) -> HttpResponse:
    return render(request, "app/home.html", {})


def cursos(request) -> HttpResponse:
    return render(request, "app/cursos.html", {})


def tutoriais(request) -> HttpResponse:
    return render(request, "app/tutoriais.html", {})


def comunidade(request) -> HttpResponse:
    return render(request, "app/comunidade.html", {})


def meuperfil(request) -> HttpResponse:
    return render(request, "app/meuperfil.html", {})
