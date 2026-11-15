import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import UserPreferences

User = get_user_model()
PASSWORD = "Senha-forte-123"


class UserPreferencesSignalTests(TestCase):
    def test_creating_a_user_creates_default_preferences(self):
        user = User.objects.create_user(username="ana", password=PASSWORD)

        preferences = UserPreferences.objects.get(user=user)
        self.assertEqual(preferences.theme, "dark")
        self.assertEqual(preferences.contrast, "normal")
        self.assertEqual(preferences.font_size, 1.0)

    def test_saving_a_user_saves_its_preferences(self):
        user = User.objects.create_user(username="ana", password=PASSWORD)
        user.preferences.theme = "light"
        user.save()

        self.assertEqual(UserPreferences.objects.get(user=user).theme, "light")

    def test_saving_a_user_without_preferences_does_not_fail(self):
        user = User.objects.create_user(username="ana", password=PASSWORD)
        UserPreferences.objects.filter(user=user).delete()

        user = User.objects.get(pk=user.pk)
        user.save()

        self.assertFalse(UserPreferences.objects.filter(user=user).exists())


class UserPreferencesContextProcessorTests(TestCase):
    def test_anonymous_user_gets_no_preferences(self):
        response = self.client.get(reverse("learning:home"))

        self.assertIsNone(response.context["user_preferences"])

    def test_logged_in_user_gets_their_preferences(self):
        user = User.objects.create_user(username="ana", password=PASSWORD)
        self.client.force_login(user)

        response = self.client.get(reverse("learning:home"))

        self.assertEqual(response.context["user_preferences"], user.preferences)

    def test_missing_preferences_are_created(self):
        user = User.objects.create_user(username="ana", password=PASSWORD)
        UserPreferences.objects.filter(user=user).delete()
        self.client.force_login(user)

        response = self.client.get(reverse("learning:home"))

        self.assertEqual(
            response.context["user_preferences"], UserPreferences.objects.get(user=user)
        )


class UpdatePreferencesViewTests(TestCase):
    url = reverse("accounts:update_preferences")

    def setUp(self):
        self.user = User.objects.create_user(username="ana", password=PASSWORD)
        self.client.force_login(self.user)

    def post_json(self, data):
        return self.client.post(
            self.url, data=json.dumps(data), content_type="application/json"
        )

    def preferences(self):
        return UserPreferences.objects.get(user=self.user)

    def test_anonymous_request_is_ignored(self):
        self.client.logout()

        response = self.post_json({"theme": "light"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ignored")
        self.assertEqual(self.preferences().theme, "dark")

    def test_updates_every_field(self):
        response = self.post_json(
            {"theme": "light", "contrast": "high", "font_size": 1.5}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "status": "success",
                "updated_fields": ["theme", "contrast", "font_size"],
            },
        )
        preferences = self.preferences()
        self.assertEqual(preferences.theme, "light")
        self.assertEqual(preferences.contrast, "high")
        self.assertEqual(preferences.font_size, 1.5)

    def test_updates_only_the_fields_sent(self):
        response = self.post_json({"contrast": "high"})

        self.assertEqual(response.json()["updated_fields"], ["contrast"])
        preferences = self.preferences()
        self.assertEqual(preferences.contrast, "high")
        self.assertEqual(preferences.theme, "dark")

    def test_empty_request_changes_nothing(self):
        response = self.post_json({})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["updated_fields"], [])

    def test_font_size_sent_as_text_is_accepted(self):
        response = self.post_json({"font_size": "1.2"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.preferences().font_size, 1.2)

    def test_accepts_form_data(self):
        response = self.client.post(self.url, {"theme": "light"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.preferences().theme, "light")

    def test_creates_missing_preferences(self):
        UserPreferences.objects.filter(user=self.user).delete()

        response = self.post_json({"theme": "light"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.preferences().theme, "light")

    def test_rejects_invalid_values(self):
        cases = [
            ({"theme": "system"}, "Opção de tema inválida"),
            ({"contrast": "max"}, "Opção de contraste inválida"),
            ({"font_size": "grande"}, "Tamanho de fonte inválido"),
            ({"font_size": [1.0]}, "Tamanho de fonte inválido"),
            ({"font_size": 3.0}, "Tamanho de fonte não permitido"),
        ]
        for data, message in cases:
            with self.subTest(data=data):
                response = self.post_json(data)

                self.assertEqual(response.status_code, 400)
                self.assertIn(message, response.content.decode())

        preferences = self.preferences()
        self.assertEqual(preferences.theme, "dark")
        self.assertEqual(preferences.contrast, "normal")
        self.assertEqual(preferences.font_size, 1.0)

    def test_invalid_value_discards_the_whole_request(self):
        response = self.post_json({"theme": "light", "contrast": "max"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.preferences().theme, "dark")

    def test_get_is_not_allowed(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)


class SignUpViewTests(TestCase):
    url = reverse("accounts:signup")

    def test_renders_the_form(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/signup.html")

    def test_valid_signup_creates_the_user_and_goes_to_login(self):
        response = self.client.post(
            self.url,
            {"username": "ana", "password1": PASSWORD, "password2": PASSWORD},
        )

        self.assertRedirects(response, reverse("accounts:login"))
        user = User.objects.get(username="ana")
        self.assertTrue(UserPreferences.objects.filter(user=user).exists())

    def test_new_account_keeps_the_preferences_chosen_before_signing_up(self):
        self.client.post(
            self.url,
            {
                "username": "ana",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "theme": "light",
                "contrast": "high",
                "font_size": "1.5",
            },
        )

        preferences = User.objects.get(username="ana").preferences
        self.assertEqual(preferences.theme, "light")
        self.assertEqual(preferences.contrast, "high")
        self.assertEqual(preferences.font_size, 1.5)

    def test_invalid_preferences_do_not_block_signing_up(self):
        response = self.client.post(
            self.url,
            {
                "username": "ana",
                "password1": PASSWORD,
                "password2": PASSWORD,
                "theme": "rosa",
            },
        )

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertEqual(User.objects.get(username="ana").preferences.theme, "dark")

    def test_mismatched_passwords_show_an_error(self):
        response = self.client.post(
            self.url,
            {"username": "ana", "password1": PASSWORD, "password2": "outra-senha"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="ana").exists())


class LogInOutViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ana", password=PASSWORD)

    def test_renders_the_form(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/login.html")

    def test_valid_login_goes_to_home(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "ana", "password": PASSWORD}
        )

        self.assertRedirects(response, reverse("learning:home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "ana", "password": "errada"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_goes_to_home(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("learning:home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class SavedPreferencesTests(TestCase):
    pages = (
        "learning:home",
        "learning:cursos",
        "learning:tutoriais",
        "learning:comunidade",
        "learning:acessibilidade",
        "learning:meuperfil",
        "spelling:game",
        "accounts:login",
        "accounts:signup",
    )

    def setUp(self):
        self.user = User.objects.create_user(username="ana", password=PASSWORD)

    def assertPreferencesApplied(self, response, theme, contrast, font_size):
        self.assertContains(response, f'data-theme="{theme}"')
        self.assertContains(response, f'data-contrast="{contrast}"')
        self.assertContains(response, f"--fs-step: {font_size}")

    def test_every_page_applies_the_account_preferences(self):
        update = {"theme": "light", "contrast": "high", "font_size": 1.5}
        UserPreferences.objects.filter(user=self.user).update(**update)
        # log in with a fresh instance: logging in saves the user, and the post_save
        # signal would also save the old preferences cached on self.user
        self.client.force_login(User.objects.get(pk=self.user.pk))

        for name in self.pages:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))

                self.assertPreferencesApplied(response, "light", "high", "1.5")

    def test_every_page_applies_the_browser_preferences_when_logged_out(self):
        # without an account the choices live in localStorage, read by base.html
        public_pages = [name for name in self.pages if name != "learning:meuperfil"]
        for name in public_pages:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))

                self.assertContains(response, 'localStorage.getItem("izone-theme")')
                self.assertNotContains(response, "data-theme=")

    def test_preferences_are_kept_after_logging_out_and_in_again(self):
        login = {"username": "ana", "password": PASSWORD}
        self.client.post(reverse("accounts:login"), login)
        self.client.post(
            reverse("accounts:update_preferences"),
            data=json.dumps({"theme": "light", "font_size": 1.3}),
            content_type="application/json",
        )
        self.client.post(reverse("accounts:logout"))

        self.client.post(reverse("accounts:login"), login)
        response = self.client.get(reverse("learning:home"))

        self.assertPreferencesApplied(response, "light", "normal", "1.3")
