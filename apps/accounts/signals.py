from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import UserPreferences


UserModel = get_user_model()


@receiver(post_save, sender=UserModel)
def create_user_prefencer(sender, instance, created, **kwargs):
    if created:
        UserPreferences.objects.create(user=instance)


@receiver(post_save, sender=UserModel)
def save_user_prefencer(sender, instance, **kwargs):
    if hasattr(instance, "preferences"):
        instance.preferences.save()
