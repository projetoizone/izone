"""
This module (views.py) corresponds to the 'Controller' in the MVC Architecture.

The MVC 'View' is the 'templates/' folder
"""

from django.shortcuts import render
from django.http import HttpResponse


def home(request) -> HttpResponse:
    return render(request, "learning/home.html", {})


def cursos(request) -> HttpResponse:
    return render(request, "learning/cursos.html", {})


def tutoriais(request) -> HttpResponse:
    return render(request, "learning/tutoriais.html", {})


def comunidade(request) -> HttpResponse:
    return render(request, "learning/comunidade.html", {})


def meuperfil(request) -> HttpResponse:
    return render(request, "learning/meuperfil.html", {})
