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

from .forms import UserSignUpForm
from .models import UserPreferences
from .preferences import InvalidPreference, clean_preferences, update_preferences


class SignUpView(CreateView):
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:login")
    form_class = UserSignUpForm

    def form_valid(self, form):
        response = super().form_valid(form)

        # new accounts start with the theme, contrast and font size chosen before signing up
        try:
            cleaned = clean_preferences(self.request.POST)
        except InvalidPreference:
            cleaned = {}
        update_preferences(self.object.preferences, cleaned)

        return response


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

        try:
            cleaned = clean_preferences(new_preferences)
        except InvalidPreference as error:
            return HttpResponseBadRequest(str(error))

        user_preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
        update_preferences(user_preferences, cleaned)

        return JsonResponse({"status": "success", "updated_fields": list(cleaned)})
