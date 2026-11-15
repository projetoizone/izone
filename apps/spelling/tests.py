from django.test import TestCase
from django.urls import reverse


class GameViewTests(TestCase):
    def test_game_page_renders(self):
        response = self.client.get(reverse("spelling:game"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "spelling/index.html")

    def test_game_page_uses_the_shared_layout(self):
        response = self.client.get(reverse("spelling:game"))

        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, 'data-action="toggle-contrast"')
        self.assertContains(response, "js/game.js")

    def test_braille_display_label_is_announced(self):
        response = self.client.get(reverse("spelling:game"))

        # aria-label is ignored on a plain div; the group role makes it announced
        self.assertRegex(
            response.content.decode(),
            r'id="braille-display"[^>]*role="group"[^>]*aria-label="[^"]+"',
        )
