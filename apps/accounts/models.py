"""
This module (models.py) corresponds to the 'Model' in the MVC Architecture.
"""

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser

from .constants import DEFAULT_THEME, DEFAULT_CONTRAST, DEFAULT_FONT_SIZE
from .enums import Theme, Contrast, FontSize


class User(AbstractUser):
    pass


class UserPreferences(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="preferences"
    )

    theme = models.CharField(choices=Theme.choices, default=DEFAULT_THEME)
    contrast = models.CharField(choices=Contrast.choices, default=DEFAULT_CONTRAST)
    font_size = models.FloatField(
        choices=FontSize.choices, default=DEFAULT_FONT_SIZE.value
    )
