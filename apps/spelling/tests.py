from django.test import TestCase
from django.urls import reverse


class GameViewTests(TestCase):
    def test_game_page_renders(self):
        response = self.client.get(reverse("spelling:game"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "spelling/index.html")
