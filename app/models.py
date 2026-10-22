"""
This module (models.py) corresponds to the 'Model' in the MVC Architecture.
"""

from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # Other user info here
