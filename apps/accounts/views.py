"""
This module (views.py) corresponds to the 'Controller' in the MVC Architecture.

The MVC 'View' is the 'templates/' folder
"""

import json

from django.contrib.auth.views import LoginView
from django.http import HttpResponseBadRequest, JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic.edit import CreateView

from .enums import Theme, Contrast, FontSize
from .forms import UserSignUpForm
from .models import UserPreferences


class SignUpView(CreateView):
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:login")
    form_class = UserSignUpForm


class LogInView(LoginView):
    template_name = "accounts/login.html"


class UpdatePreferencesView(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"status": "ignored", "message": "Usuário Anônimo"}, status=200
            )

        try:
            new_preferences = json.loads(request.body)
        except json.JSONDecodeError:
            new_preferences = request.POST

        user_preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
        updated_fields = []

        if theme := new_preferences.get("theme"):
            if theme not in Theme.values:
                return HttpResponseBadRequest(
                    "Opção de tema inválida. Temas disponíveis: 'light', 'dark' e 'system'."
                )
            user_preferences.theme = theme
            updated_fields.append("theme")

        if contrast := new_preferences.get("contrast"):
            if contrast not in Contrast.values:
                return HttpResponseBadRequest(
                    "Opção de contraste inválida. Contrastes disponíveis: 'normal' or 'high'."
                )
            user_preferences.contrast = contrast
            updated_fields.append("contrast")

        if font_size := new_preferences.get("font_size"):
            try:
                font_size = float(font_size)
            except (ValueError, TypeError):
                return HttpResponseBadRequest("Tamanho de fonte inválido.")

            if font_size not in FontSize.values:
                return HttpResponseBadRequest("Tamanho de fonte não permitido.")

            user_preferences.font_size = float(font_size)
            updated_fields.append("font_size")

        if updated_fields:
            user_preferences.save(update_fields=updated_fields)

        return JsonResponse({"status": "success", "updated_fields": updated_fields})
