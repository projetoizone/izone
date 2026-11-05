"""
This module (views.py) corresponds to the 'Controller' in the MVC Architecture.

The MVC 'View' is the 'templates/' folder
"""

from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView

from .forms import UserSignUpForm


class SignUpView(CreateView):
    template_name = "accounts/signup.html"
    success_url = reverse_lazy("accounts:login")
    form_class = UserSignUpForm


class LogInView(LoginView):
    template_name = "accounts/login.html"
