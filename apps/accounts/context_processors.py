from .models import UserPreferences


def user_preferences(request):
    preferences = None

    if request.user.is_authenticated:
        preferences, _ = UserPreferences.objects.get_or_create(user=request.user)

    return {"user_preferences": preferences}
