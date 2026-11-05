from django.shortcuts import render

from django.urls import reverse_lazy
from django.views.generic import TemplateView


class GameView(TemplateView):
    template_name = "spelling/index.html"
