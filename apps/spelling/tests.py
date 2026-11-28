from unittest.mock import Mock, patch

import requests
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from . import dicionario_aberto


class GameViewTests(TestCase):
    def test_game_page_renders(self):
        response = self.client.get(reverse("spelling:game"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "spelling/index.html")

    def test_game_page_uses_the_shared_layout(self):
        response = self.client.get(reverse("spelling:game"))

        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, 'data-action="theme"')
        self.assertContains(response, "js/game.js")

    def test_braille_display_label_is_announced(self):
        response = self.client.get(reverse("spelling:game"))

        # aria-label is ignored on a plain div; the group role makes it announced
        self.assertRegex(
            response.content.decode(),
            r'id="braille-display"[^>]*role="group"[^>]*aria-label="[^"]+"',
        )

    def test_game_page_follows_the_site_layout(self):
        html = self.client.get(reverse("spelling:game")).content.decode()

        self.assertIn('<h1 class="page-title">', html)
        self.assertIn('class="lede"', html)
        self.assertIn('<div class="field">', html)
        self.assertRegex(html, r'id="next-round"[^>]*class="btn btn-primary"')
        # the game speaks through the accessibility bar, with the site speed; no voice picker of its own
        self.assertNotIn('id="voice-select"', html)
        self.assertIn('data-challenge-url="/spelling/api/desafio"', html)

    def test_courses_page_links_to_the_game(self):
        response = self.client.get(reverse("learning:cursos"))

        self.assertContains(response, f'href="{reverse("spelling:game")}"')


ENTRY_XML = (
    '<entry id="casa"><form><orth>Casa</orth></form><sense><def>\n'
    "Edifício para habitação: _uma casa moderna_.\n</def></sense></entry>"
)


def api_response(data, status=200):
    response = Mock(status_code=status)
    response.json.return_value = data
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(str(status))
    return response


def dicionario_aberto_api(*words):
    """Fakes the API: /random gives each word in turn and /word/<w> gives its entry."""
    queue = list(words)

    def get(url, timeout):
        if url.endswith("/random"):
            return api_response({"word": queue.pop(0)})
        return api_response([{"word": "casa", "xml": ENTRY_XML}])

    return get


@patch("apps.spelling.dicionario_aberto.requests.get")
class ChallengeApiTests(TestCase):
    def test_returns_a_word_with_its_definition(self, get):
        get.side_effect = dicionario_aberto_api("casa")

        response = self.client.get(reverse("spelling:challenge"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "word": "casa",
                "definition": "Edifício para habitação: uma casa moderna.",
                "example": "",
            },
        )

    def test_skips_words_the_braille_table_cannot_show(self, get):
        get.side_effect = dicionario_aberto_api("ação", "pé", "guarda-chuva", "casa")

        response = self.client.get(reverse("spelling:challenge"))

        self.assertEqual(response.json()["word"], "casa")

    def test_gives_up_after_a_few_words(self, get):
        get.side_effect = dicionario_aberto_api(*["ação"] * 8)

        response = self.client.get(reverse("spelling:challenge"))

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"], dicionario_aberto.NO_WORD)

    def test_reports_when_the_api_is_down(self, get):
        get.side_effect = requests.Timeout()

        response = self.client.get(reverse("spelling:challenge"))

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"], dicionario_aberto.UNAVAILABLE)

    def test_reports_an_unexpected_answer(self, get):
        get.return_value = api_response({"wid": 1})

        response = self.client.get(reverse("spelling:challenge"))

        self.assertEqual(response.status_code, 502)

    def test_word_without_definition(self, get):
        def api(url, timeout):
            if url.endswith("/random"):
                return api_response({"word": "casa"})
            return api_response([{"xml": "<entry><broken"}])

        get.side_effect = api

        response = self.client.get(reverse("spelling:challenge"))

        self.assertEqual(response.json()["definition"], dicionario_aberto.NO_DEFINITION)

    def test_only_answers_get(self, get):
        response = self.client.post(reverse("spelling:challenge"))

        self.assertEqual(response.status_code, 405)


class BrailleCellTests(TestCase):
    def test_dots_fill_the_cell_column_by_column(self):
        # game.js adds dots 1 to 6 in order; in Braille 1-2-3 are the left column, 4-5-6 the right
        css = (settings.BASE_DIR / "public" / "css" / "braille.css").read_text()

        self.assertRegex(css, r"\.braille-cell\s*\{[^}]*grid-auto-flow:\s*column")
