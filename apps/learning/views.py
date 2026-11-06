"""
This module (views.py) corresponds to the 'Controller' in the MVC Architecture.

The MVC 'View' is the 'templates/' folder
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


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
