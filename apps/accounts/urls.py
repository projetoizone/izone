from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"
urlpatterns = [
    path("signup", views.SignUpView.as_view(), name="signup"),
    path("login", views.LogInView.as_view(), name="login"),
    path("logout", LogoutView.as_view(), name="logout"),
    path(
        "update-preferences",
        views.UpdatePreferencesView.as_view(),
        name="update_preferences",
    ),
]
