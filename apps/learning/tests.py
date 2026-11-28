import itertools
import json
import re
from html.parser import HTMLParser
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.accounts.enums import Contrast, Theme
from apps.learning import nasa_images, wikipedia

User = get_user_model()
PASSWORD = "Senha-forte-123"

# pages that use the shared layout and can be opened without logging in
PAGES = (
    "learning:home",
    "learning:cursos",
    "learning:tutoriais",
    "learning:comunidade",
    "learning:acessibilidade",
    "learning:astronomia",
    "learning:wikipedia",
    "accounts:login",
    "accounts:signup",
    "spelling:game",
)


class PublicPagesTests(TestCase):
    pages = (
        ("learning:home", "learning/home.html"),
        ("learning:cursos", "learning/cursos.html"),
        ("learning:tutoriais", "learning/tutoriais.html"),
        ("learning:comunidade", "learning/comunidade.html"),
        ("learning:acessibilidade", "learning/acessibilidade.html"),
        ("learning:astronomia", "learning/astronomia.html"),
        ("learning:wikipedia", "learning/wikipedia.html"),
    )

    def test_pages_render(self):
        for name, template in self.pages:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)


class MeuPerfilViewTests(TestCase):
    url = reverse("learning:meuperfil")

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(self.url)

        # assertRedirects also checks that the login page itself loads
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    def test_login_returns_to_the_profile(self):
        User.objects.create_user(username="ana", password=PASSWORD)

        response = self.client.post(
            f"{reverse('accounts:login')}?next={self.url}",
            {"username": "ana", "password": PASSWORD},
        )

        self.assertRedirects(response, self.url)

    def test_logged_in_user_sees_the_profile(self):
        user = User.objects.create_user(username="ana", password=PASSWORD)
        self.client.force_login(user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "learning/meuperfil.html")


class SkipLinkTests(TestCase):
    def test_every_page_can_skip_to_the_main_content(self):
        user = User.objects.create_user(username="ana", password=PASSWORD)
        for name in PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))

                self.assertContains(response, 'href="#conteudo-principal"')
                self.assertContains(response, '<main id="conteudo-principal"')

        self.client.force_login(user)
        response = self.client.get(reverse("learning:meuperfil"))
        self.assertContains(response, 'href="#conteudo-principal"')
        self.assertContains(response, '<main id="conteudo-principal"')


class AcessibilidadeViewTests(TestCase):
    url = reverse("learning:acessibilidade")

    def test_footer_links_to_the_page(self):
        response = self.client.get(reverse("learning:home"))

        self.assertContains(
            response, f'<a href="{self.url}">ACESSIBILIDADE</a>', html=True
        )

    def test_footer_marks_the_current_page(self):
        response = self.client.get(self.url)

        self.assertContains(
            response,
            f'<a href="{self.url}" aria-current="page">ACESSIBILIDADE</a>',
            html=True,
        )

    def test_links_inside_the_page_point_to_existing_sections(self):
        html = self.client.get(self.url).content.decode()

        targets = re.findall(r'href="#([^"]+)"', html)
        self.assertGreater(len(targets), 1)
        for target in targets:
            with self.subTest(target=target):
                self.assertIn(f'id="{target}"', html)


class SymbolsReadAloud(HTMLParser):
    """Collects emoji and symbols that a screen reader would read out by name.

    A symbol is fine inside aria-hidden="true", or inside a link or button whose
    aria-label replaces its content.
    """

    SYMBOLS = re.compile(
        "[\U0001f300-\U0001faff\u2600-\u27bf\u2b00-\u2bff"
        "\u25a0-\u25ff\u2190-\u21ff\u2300-\u23ff]"
    )
    VOID = frozenset(
        {"area", "br", "col", "embed", "hr", "img", "input", "link", "meta", "wbr"}
    )

    def __init__(self):
        super().__init__()
        self.stack = []
        self.found = []

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        attrs = dict(attrs)
        silenced = (
            attrs.get("aria-hidden") == "true"
            or (tag in ("a", "button") and bool(attrs.get("aria-label")))
            or tag in ("script", "style")
        )
        self.stack.append((tag, silenced))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.SYMBOLS.search(data) and not any(s for _, s in self.stack):
            self.found.append(data.strip())


class DecorativeSymbolsTests(TestCase):
    def assertNoSymbolsReadAloud(self, response):
        parser = SymbolsReadAloud()
        parser.feed(response.content.decode())
        self.assertEqual(parser.found, [])

    def test_symbols_are_hidden_from_screen_readers(self):
        for name in PAGES:
            with self.subTest(page=name):
                self.assertNoSymbolsReadAloud(self.client.get(reverse(name)))

        self.client.force_login(User.objects.create_user(username="ana"))
        self.assertNoSymbolsReadAloud(self.client.get(reverse("learning:meuperfil")))

    def test_tutorial_durations_have_a_spoken_label(self):
        response = self.client.get(reverse("learning:tutoriais"))

        self.assertContains(response, '<span class="sr-only">Duração:</span>', count=4)


URLOPEN = "apps.learning.nasa_images.urlopen"


def nasa_item(nasa_id="PIA14417", title="Weighing in on the Dumbbell Nebula", **data):
    """An item as the NASA Image and Video Library API returns it."""
    base = f"https://images-assets.nasa.gov/image/{nasa_id}/{nasa_id}"
    return {
        "href": f"{base}/collection.json",
        "data": [
            {
                "nasa_id": nasa_id,
                "title": title,
                "media_type": "image",
                "date_created": "2011-08-10T21:00:09Z",
                "center": "JPL",
                "description": "The <b>Dumbbell nebula</b>, also known as &quot;Messier 27&quot;, "
                "pumps out infrared light.",
                "secondary_creator": "NASA/JPL-Caltech",
                "keywords": ["Nebula", "Spitzer Space Telescope", "nebula"],
                **data,
            }
        ],
        "links": [
            {
                "href": f"{base}~large.jpg",
                "rel": "alternate",
                "render": "image",
                "width": 1920,
                "height": 960,
            },
            {
                "href": f"{base}~medium.jpg",
                "rel": "alternate",
                "render": "image",
                "width": 1280,
                "height": 640,
            },
            {
                "href": f"{base}~small.jpg",
                "rel": "alternate",
                "render": "image",
                "width": 640,
                "height": 320,
            },
            {"href": f"{base}~thumb.jpg", "rel": "preview", "render": "image"},
            {"href": f"{base}~orig.jpg", "rel": "canonical", "render": "image"},
        ],
    }


def nasa_api(*items, total=None):
    """A urlopen replacement that answers every request with these items."""
    body = {
        "collection": {
            "items": list(items),
            "metadata": {"total_hits": len(items) if total is None else total},
        }
    }
    return lambda request, timeout: BytesIO(json.dumps(body).encode())


def strip_tags(html):
    html = re.sub(
        r'<(\w+)[^>]*aria-hidden="true"[^>]*>.*?</\1>', "", html, flags=re.DOTALL
    )
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


class ScreenReaderStructureTests(TestCase):
    def pages(self):
        for name in PAGES:
            yield name, self.client.get(reverse(name)).content.decode()
        # the astronomy pages also show results and an image, from a mocked NASA API
        cache.clear()
        with patch(
            URLOPEN,
            side_effect=nasa_api(
                nasa_item(), nasa_item("PIA04216", "Ant Nebula"), total=30
            ),
        ):
            url = reverse("learning:astronomia")
            yield (
                "astronomy results",
                self.client.get(url + "?q=nebula&pagina=2").content.decode(),
            )
            url = reverse("learning:astronomia_imagem", args=["PIA14417"])
            yield "astronomy image", self.client.get(url + "?q=nebula").content.decode()
        # and the Wikipedia pages, from a mocked Wikipedia API
        cache.clear()
        with patch(
            WIKI_URLOPEN,
            side_effect=wiki_api(
                wiki_result(),
                wiki_result("Clorofila", index=2),
                total=30,
                suggestion="fotossíntese",
                article=wiki_article(),
                image=wiki_image(),
            ),
        ):
            url = reverse("learning:wikipedia")
            yield (
                "wikipedia results",
                self.client.get(url + "?q=fotosintese&pagina=2").content.decode(),
            )
            url = reverse("learning:wikipedia_artigo", args=["Fotossíntese"])
            yield "wikipedia article", self.client.get(url + "?q=x").content.decode()
        self.client.force_login(User.objects.create_user(username="ana"))
        yield (
            "learning:meuperfil",
            self.client.get(reverse("learning:meuperfil")).content.decode(),
        )

    def test_every_page_has_one_h1_and_no_skipped_heading_levels(self):
        for name, html in self.pages():
            with self.subTest(page=name):
                levels = [int(level) for level in re.findall(r"<h([1-6])\b", html)]

                self.assertEqual(levels.count(1), 1)
                self.assertEqual(levels[0], 1)
                for previous, level in itertools.pairwise(levels):
                    self.assertLessEqual(level, previous + 1)

    def test_accessible_names_start_with_the_visible_text(self):
        # WCAG 2.5.3: someone using voice control says what they see
        pattern = r'<(a|button)\b([^>]*\baria-label="([^"]+)"[^>]*)>(.*?)</\1>'
        for name, html in self.pages():
            for _, _, label, content in re.findall(pattern, html, flags=re.DOTALL):
                visible = strip_tags(content)
                if re.search(r"\w", visible):
                    with self.subTest(page=name, visible=visible):
                        self.assertTrue(
                            label.lower().startswith(visible.lower()), label
                        )

    def test_links_in_the_main_content_have_distinct_names(self):
        for name, html in self.pages():
            with self.subTest(page=name):
                main = html[html.index("<main") : html.index("</main>")]
                names = [
                    strip_tags(link)
                    for link in re.findall(r"<a\b.*?</a>", main, flags=re.DOTALL)
                ]

                repeated = {n for n in names if names.count(n) > 1}
                self.assertEqual(repeated, set())

    def test_the_community_sidebar_is_named_by_its_heading(self):
        html = self.client.get(reverse("learning:comunidade")).content.decode()

        self.assertRegex(html, r'<aside\b[^>]*aria-labelledby="populares-h"')
        self.assertIn('id="populares-h"', html)


class ReadAloudSpeedTests(TestCase):
    def test_profile_slider_uses_the_same_speeds_as_the_accessibility_bar(self):
        # accessibility.js offers 0.5x to 2x in steps of 0.25
        self.client.force_login(User.objects.create_user(username="ana"))

        response = self.client.get(reverse("learning:meuperfil"))

        self.assertContains(
            response,
            'type="range" id="pref-velocidade" name="velocidade" min="0.5" max="2" '
            'step="0.25" value="1" aria-valuetext="1x"',
        )
        self.assertContains(response, 'id="pref-velocidade-valor" aria-hidden="true"')

    def test_accessibility_page_documents_the_speed_control(self):
        response = self.client.get(reverse("learning:acessibilidade"))

        self.assertContains(response, '<th scope="row">Velocidade</th>')


STYLE_CSS = settings.BASE_DIR / "public" / "css" / "style.css"


def css_themes():
    """The custom properties of each theme in style.css, with var() resolved."""
    css = STYLE_CSS.read_text()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    blocks = {
        selector.strip(): dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body))
        for selector, body in re.findall(
            r"^(:root[^{]*)\{([^}]*)\}", css, flags=re.MULTILINE
        )
    }
    light, high = ':root[data-theme="light"]', ':root[data-contrast="high"]'
    layers = {
        "dark": (":root",),
        "light": (":root", light),
        "high contrast": (":root", high),
        "light high contrast": (":root", light, high, light + '[data-contrast="high"]'),
        "yellow": (":root", ':root[data-theme="yellow"]'),
        "sepia": (":root", ':root[data-theme="sepia"]'),
    }
    themes = {}
    for theme, selectors in layers.items():
        props = {}
        for selector in selectors:
            props.update(blocks[selector])
        for name, value in props.items():
            while value.startswith("var("):
                value = props[value[4:-1]]
            props[name] = value
        themes[theme] = props
    return themes


def contrast(color, other):
    def luminance(hex_color):
        channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        r, g, b = (
            c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
            for c in channels
        )
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    lighter, darker = sorted((luminance(color), luminance(other)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


class ReadAloudHighlightTests(TestCase):
    def test_highlight_is_readable_and_stands_out_in_every_theme(self):
        for theme, props in css_themes().items():
            with self.subTest(theme=theme):
                # WCAG 1.4.3 for the text being read, 1.4.11 for the highlight against the page
                self.assertGreaterEqual(
                    contrast(props["--reading-text"], props["--reading-bg"]), 4.5
                )
                self.assertGreaterEqual(
                    contrast(props["--reading-bg"], props["--bg"]), 3
                )

    def test_script_and_stylesheet_use_the_same_highlights(self):
        css = STYLE_CSS.read_text()
        js = (settings.BASE_DIR / "public" / "js" / "accessibility.js").read_text()

        self.assertRegex(
            css,
            r"::highlight\(tts-sentence\) \{ background-color: var\(--reading-bg\); "
            r"color: var\(--reading-text\);",
        )
        for name in ("tts-sentence", "tts-word"):
            with self.subTest(highlight=name):
                self.assertIn(f"::highlight({name})", css)
                self.assertIn(f'highlight("{name}"', js)

    def test_accessibility_page_documents_the_highlight(self):
        response = self.client.get(reverse("learning:acessibilidade"))

        self.assertContains(
            response, "A frase que está sendo lida fica destacada na tela"
        )


class MainMenuTests(TestCase):
    def test_every_page_shows_the_main_menu(self):
        for name in PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))

                self.assertContains(response, '<nav class="main-nav" aria-label="Principal">')


class ThemeSelectorTests(TestCase):
    option = re.compile(
        r'<option value="([^"]+)" data-set-theme="([^"]+)" '
        r'data-set-contrast="([^"]+)">([^<]+)</option>'
    )

    def options(self):
        html = self.client.get(reverse("learning:home")).content.decode()
        return self.option.findall(html)

    def test_every_page_has_a_labelled_theme_list(self):
        for name in PAGES:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))

                self.assertContains(response, '<label class="sr-only" for="a11y-tema">Tema</label>')
                self.assertContains(
                    response, '<select id="a11y-tema" data-action="theme">'
                )
                self.assertNotContains(response, 'data-action="toggle-contrast"')
                self.assertNotContains(response, 'data-action="toggle-theme"')

    def test_offers_six_themes_that_can_be_saved(self):
        options = self.options()

        self.assertEqual(len(options), 6)
        self.assertEqual(
            len({(theme, contrast) for _, theme, contrast, _ in options}), 6
        )
        for value, theme, contrast, label in options:
            with self.subTest(option=label):
                self.assertIn(theme, Theme.values)
                self.assertIn(contrast, Contrast.values)

    def test_every_theme_has_colours(self):
        css = STYLE_CSS.read_text()

        for _, theme, contrast, label in self.options():
            with self.subTest(option=label):
                selector = ":root"
                if theme != "dark":
                    selector += f'[data-theme="{theme}"]'
                if contrast == "high":
                    selector += '[data-contrast="high"]'
                self.assertIn(selector + " {", css)

    def test_colours_meet_wcag_contrast_in_every_theme(self):
        text = [("--text", bg) for bg in ("--bg", "--bg-elevated", "--bg-input")]
        text += [
            (fg, bg)
            for fg in ("--text-muted", "--link", "--danger")
            for bg in ("--bg", "--bg-elevated")
        ]
        text += [("--accent-ink", "--accent")]
        # borders of fields and cards, and the focus outline (WCAG 1.4.11)
        ui = [("--border", bg) for bg in ("--bg", "--bg-elevated", "--bg-input")]
        ui += [("--focus-ring", bg) for bg in ("--bg", "--bg-elevated")]

        for theme, props in css_themes().items():
            for pairs, minimum in ((text, 4.5), (ui, 3)):
                for fg, bg in pairs:
                    with self.subTest(theme=theme, colours=f"{fg} on {bg}"):
                        self.assertGreaterEqual(contrast(props[fg], props[bg]), minimum)

    def test_links_in_text_are_underlined(self):
        # in most themes links differ from the text by colour alone (WCAG 1.4.1)
        self.assertRegex(
            STYLE_CSS.read_text(),
            r"main a:not\(\.btn, \.card\), \.site-footer a \{ text-decoration: underline;",
        )

    def test_accessibility_page_describes_every_theme(self):
        response = self.client.get(reverse("learning:acessibilidade"))

        for _, _, _, label in self.options():
            with self.subTest(option=label):
                self.assertContains(response, f"<strong>{label}:</strong>")


class PrototypePagesTests(TestCase):
    # prototype/views has static copies of the pages for GitHub Pages; they load
    # public/js/accessibility.js and still use the C and ◐ buttons
    def test_accessibility_script_handles_every_button_of_the_static_pages(self):
        js = (settings.BASE_DIR / "public" / "js" / "accessibility.js").read_text()
        pages = sorted((settings.BASE_DIR / "prototype" / "views").glob("*.html"))

        self.assertTrue(pages)
        for page in pages:
            html = page.read_text()
            self.assertIn("public/js/accessibility.js", html)
            for action in set(re.findall(r'data-action="([^"]+)"', html)):
                with self.subTest(page=page.name, action=action):
                    self.assertIn(f"""'[data-action="{action}"]'""", js)


class ZoomTests(TestCase):
    def test_accessibility_page_explains_browser_zoom(self):
        response = self.client.get(reverse("learning:acessibilidade"))

        self.assertContains(response, "<kbd>Ctrl</kbd> + <kbd>+</kbd> aumenta")

    def test_layouts_with_a_sidebar_can_stack(self):
        # fixed grid columns don't reflow at 400% zoom; .with-sidebar stacks when needed
        for name in ("learning:cursos", "learning:comunidade"):
            with self.subTest(page=name):
                html = self.client.get(reverse(name)).content.decode()

                self.assertIn('class="with-sidebar"', html)
                self.assertNotIn("grid-template-columns", html)


class NasaApiMixin:
    def setUp(self):
        cache.clear()
        patcher = patch(URLOPEN, side_effect=nasa_api(nasa_item()))
        self.urlopen = patcher.start()
        self.addCleanup(patcher.stop)

    def answer(self, *items, total=None):
        self.urlopen.side_effect = nasa_api(*items, total=total)

    def requested(self):
        """The query string of the last request to the NASA API."""
        request = self.urlopen.call_args.args[0]
        self.assertTrue(
            request.full_url.startswith("https://images-api.nasa.gov/search?")
        )
        self.assertIn("timeout", self.urlopen.call_args.kwargs)
        return {k: v[0] for k, v in parse_qs(urlsplit(request.full_url).query).items()}


class SpaceImageSearchTests(NasaApiMixin, TestCase):
    url = reverse("learning:astronomia")

    def search(self, query):
        return self.client.get(f"{self.url}?{query}")

    def test_courses_page_links_to_the_astronomy_page(self):
        response = self.client.get(reverse("learning:cursos"))

        self.assertContains(response, f'href="{self.url}"')

    def test_page_without_a_search_only_shows_the_form(self):
        response = self.client.get(self.url)

        self.urlopen.assert_not_called()
        self.assertContains(response, '<label for="id_q">Assunto, em inglês</label>')
        self.assertContains(response, 'aria-describedby="id_q_helptext"')
        self.assertContains(response, '<p class="field-hint" id="id_q_helptext">')
        self.assertContains(response, "<legend>Período, opcional</legend>")
        self.assertNotContains(response, 'id="resultados-h"')

    def test_topics_have_portuguese_names_and_search_in_english(self):
        response = self.client.get(self.url)

        self.assertContains(
            response,
            f'<a class="btn btn-outline" href="{self.url}?q=black%20hole">Buracos negros</a>',
            html=True,
        )

    def test_search_asks_the_nasa_for_images_of_the_subject(self):
        response = self.search("q=nebula")

        self.assertEqual(
            self.requested(),
            {"q": "nebula", "media_type": "image", "page": "1", "page_size": "12"},
        )
        self.assertContains(
            response,
            "<title>nebula, página 1 de 1 - Imagens astronômicas - iZone</title>",
        )
        # after searching, the focus goes to the results
        self.assertContains(
            response,
            '<h2 id="resultados-h" tabindex="-1" autofocus>Resultados para “nebula”</h2>',
        )
        self.assertContains(response, "1 imagem encontrada.")
        detail = reverse("learning:astronomia_imagem", args=["PIA14417"])
        self.assertContains(
            response,
            f'<a href="{detail}?q=nebula"><span lang="en">Weighing in on the Dumbbell Nebula</span>'
            '<span class="sr-only">, 10/08/2011</span></a>',
            html=True,
        )
        # the link already names the image, so the thumbnail is decorative
        self.assertContains(
            response,
            '<img src="https://images-assets.nasa.gov/image/PIA14417/PIA14417~thumb.jpg" alt="" loading="lazy">',
            html=True,
        )

    def test_current_topic_is_marked(self):
        response = self.search("q=nebula")

        self.assertContains(
            response,
            f'<a class="btn btn-outline" href="{self.url}?q=nebula" aria-current="true">Nebulosas</a>',
            html=True,
        )

    def test_years_narrow_the_search(self):
        self.search("q=galaxy&ano_inicio=2000&ano_fim=2010")

        params = self.requested()
        self.assertEqual(params["year_start"], "2000")
        self.assertEqual(params["year_end"], "2010")

    def test_invalid_search_shows_the_error_on_the_field(self):
        cases = {
            "q=": ("q", "Digite um assunto para pesquisar."),
            "q=galaxy&ano_inicio=1800": ("ano_inicio", "Digite um ano entre 1920 e"),
            "q=galaxy&ano_fim=abc": ("ano_fim", "Digite um ano entre 1920 e"),
            "q=galaxy&ano_inicio=2010&ano_fim=2000": (
                "ano_fim",
                "O ano final não pode ser antes do inicial.",
            ),
        }
        for query, (field, message) in cases.items():
            with self.subTest(query=query):
                response = self.search(query)

                self.urlopen.assert_not_called()
                html = response.content.decode()
                self.assertIn("<title>Erro: Imagens astronômicas - iZone</title>", html)
                self.assertIn(
                    f'<p class="field-error" id="id_{field}_error">{message}', html
                )
                tag = re.search(rf'<input [^>]*id="id_{field}"[^>]*>', html).group()
                self.assertIn('aria-invalid="true"', tag)
                self.assertIn(f"id_{field}_error", tag)
                self.assertIn("autofocus", tag)

    def test_pages_link_to_each_other_and_keep_the_search(self):
        self.answer(nasa_item(), total=30)  # 3 pages of 12

        response = self.search("q=nebula&ano_inicio=2000&pagina=2")

        self.assertEqual(self.requested()["page"], "2")
        self.assertContains(response, "30 imagens encontradas. Página 2 de 3.")
        self.assertContains(
            response, f'href="{self.url}?q=nebula&amp;ano_inicio=2000" rel="prev"'
        )
        self.assertContains(
            response,
            f'href="{self.url}?q=nebula&amp;ano_inicio=2000&amp;pagina=3" rel="next"',
        )
        detail = reverse("learning:astronomia_imagem", args=["PIA14417"])
        self.assertContains(
            response, f'href="{detail}?q=nebula&amp;ano_inicio=2000&amp;pagina=2"'
        )

    def test_first_and_last_pages_link_only_inwards(self):
        self.answer(nasa_item(), total=30)

        first = self.search("q=nebula")
        last = self.search("q=nebula&pagina=3")

        self.assertNotContains(first, 'rel="prev"')
        self.assertContains(first, 'rel="next"')
        self.assertContains(last, 'rel="prev"')
        self.assertNotContains(last, 'rel="next"')

    def test_page_number_stays_within_what_the_api_serves(self):
        for value, page in (
            ("abc", "1"),
            ("0", "1"),
            ("99999", str(nasa_images.MAX_PAGE)),
        ):
            with self.subTest(pagina=value):
                self.search(f"q=nebula&pagina={value}")

                self.assertEqual(self.requested()["page"], page)

    def test_page_past_the_last_one_links_back(self):
        self.answer(total=30)

        response = self.search("q=nebula&pagina=5")

        self.assertContains(response, "Esta pesquisa tem 3 páginas.")
        self.assertContains(
            response, f'href="{self.url}?q=nebula&amp;pagina=3" rel="prev"'
        )
        self.assertContains(
            response,
            f'<a href="{self.url}?q=nebula&amp;pagina=3">Ir para a última página</a>',
        )

    def test_no_results_suggest_searching_in_english(self):
        self.answer(total=0)

        response = self.search("q=nebulosa")

        self.assertContains(
            response, "Nenhuma imagem encontrada. A NASA descreve as imagens em inglês"
        )

    def test_unusable_items_are_left_out(self):
        unsafe = nasa_item("UNSAFE", "Unsafe links")
        for link in unsafe["links"]:
            link["href"] = "javascript:alert(1)"
        self.answer(
            nasa_item("VIDEO1", "A video", media_type="video"),
            nasa_item("NOTITLE", ""),
            unsafe,
            nasa_item(),
        )

        response = self.search("q=nebula")

        self.assertNotContains(response, "A video")
        self.assertNotContains(response, "NOTITLE")
        self.assertNotContains(response, "javascript:")
        self.assertContains(response, "Unsafe links")  # shown, without the image
        self.assertContains(response, "Weighing in on the Dumbbell Nebula")

    def test_api_failures_show_a_message(self):
        failures = {
            "offline": (URLError("no network"), nasa_images.UNAVAILABLE),
            "timeout": (TimeoutError(), nasa_images.UNAVAILABLE),
            "server error": (
                HTTPError("u", 500, "Error", {}, BytesIO(b"")),
                nasa_images.UNAVAILABLE,
            ),
            "refused": (
                HTTPError("u", 400, "Bad Request", {}, BytesIO(b"")),
                nasa_images.REFUSED,
            ),
            "not json": (
                lambda request, timeout: BytesIO(b"<html>"),
                nasa_images.UNAVAILABLE,
            ),
            "no collection": (
                lambda request, timeout: BytesIO(b"[]"),
                nasa_images.UNAVAILABLE,
            ),
        }
        for case, (failure, message) in failures.items():
            with self.subTest(case=case):
                cache.clear()
                self.urlopen.side_effect = failure

                response = self.search("q=nebula")

                self.assertEqual(response.status_code, 502)
                self.assertContains(response, "Pesquisa não concluída", status_code=502)
                self.assertContains(response, message, status_code=502)

    def test_results_are_cached(self):
        self.search("q=nebula")
        self.search("q=nebula")
        self.search("q=galaxy")

        self.assertEqual(self.urlopen.call_count, 2)


class SpaceImageDetailTests(NasaApiMixin, TestCase):
    def detail(self, nasa_id="PIA14417", query=""):
        url = reverse("learning:astronomia_imagem", args=[nasa_id])
        return self.client.get(f"{url}?{query}" if query else url)

    def test_asks_the_nasa_for_the_image(self):
        self.detail()

        self.assertEqual(self.requested(), {"nasa_id": "PIA14417"})

    def test_shows_the_image_marked_as_english(self):
        response = self.detail()

        self.assertContains(
            response,
            "<title>Weighing in on the Dumbbell Nebula - Imagens astronômicas - iZone</title>",
        )
        self.assertContains(
            response,
            '<h1 class="page-title" lang="en">Weighing in on the Dumbbell Nebula</h1>',
            html=True,
        )
        base = "https://images-assets.nasa.gov/image/PIA14417/PIA14417"
        # the largest version up to 1280px wide, with the narrower ones for small screens
        self.assertContains(
            response,
            f'<img src="{base}~medium.jpg" srcset="{base}~small.jpg 640w, {base}~medium.jpg 1280w" '
            'sizes="(min-width: 80rem) 72rem, 100vw" width="1280" height="640" '
            'alt="Weighing in on the Dumbbell Nebula" lang="en">',
            html=True,
        )
        self.assertContains(
            response, "<figcaption>Crédito: NASA/JPL-Caltech</figcaption>", html=True
        )
        self.assertContains(
            response,
            f'<a href="{base}~orig.jpg">Abrir a imagem em tamanho original</a>',
            html=True,
        )

    def test_description_is_plain_text_in_english(self):
        response = self.detail()

        self.assertContains(
            response, '<h2 id="descricao">Descrição da imagem</h2>', html=True
        )
        self.assertContains(
            response,
            '<div class="space-description" lang="en"><p>The Dumbbell nebula, also known as '
            '"Messier 27", pumps out infrared light.</p></div>',
            html=True,
        )

    def test_shows_the_facts_and_the_source(self):
        response = self.detail()

        self.assertContains(response, "<dt>Data</dt><dd>10/08/2011</dd>", html=True)
        self.assertContains(
            response,
            "<dt>Centro da NASA</dt><dd>Jet Propulsion Laboratory (JPL)</dd>",
            html=True,
        )
        self.assertContains(response, 'href="https://images.nasa.gov/details/PIA14417"')

    def test_keywords_search_for_themselves_once_each(self):
        response = self.detail()

        search = reverse("learning:astronomia")
        self.assertContains(
            response,
            f'<a class="btn btn-outline" href="{search}?q=Spitzer%20Space%20Telescope" lang="en">Spitzer Space Telescope</a>',
            html=True,
        )
        self.assertContains(response, f'href="{search}?q=Nebula"', count=1)
        self.assertNotContains(response, f'href="{search}?q=nebula"')

    def test_back_link_returns_to_the_results(self):
        search = reverse("learning:astronomia")

        from_results = self.detail(query="q=nebula&ano_fim=2010&pagina=2")
        direct = self.detail()

        self.assertContains(
            from_results,
            f'<a href="{search}?q=nebula&amp;ano_fim=2010&amp;pagina=2">Voltar aos resultados</a>',
            html=True,
        )
        self.assertContains(
            direct, f'<a href="{search}">Pesquisar imagens astronômicas</a>', html=True
        )

    def test_image_without_sized_versions_uses_the_preview(self):
        item = nasa_item()
        item["links"] = [link for link in item["links"] if link["rel"] != "alternate"]
        self.answer(item)

        response = self.detail()

        self.assertContains(
            response,
            '<img src="https://images-assets.nasa.gov/image/PIA14417/PIA14417~thumb.jpg" '
            'alt="Weighing in on the Dumbbell Nebula" lang="en">',
            html=True,
        )

    def test_unknown_image_is_not_found(self):
        for items in ((), (nasa_item("PIA00001"),), (nasa_item(media_type="video"),)):
            with self.subTest(items=len(items)):
                cache.clear()
                self.answer(*items)

                response = self.detail()

                self.assertContains(response, "Imagem não encontrada", status_code=404)

    def test_api_failure_shows_a_message(self):
        self.urlopen.side_effect = URLError("no network")

        response = self.detail()

        self.assertContains(response, "Imagem indisponível", status_code=502)
        self.assertContains(response, nasa_images.UNAVAILABLE, status_code=502)


WIKI_URLOPEN = "apps.learning.wikipedia.urlopen"
WIKI_THUMB = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/"
    "Aspen_tree_in_sunlight.jpg/250px-Aspen_tree_in_sunlight.jpg"
)


def wiki_result(title="Fotossíntese", index=1, **data):
    """A page as the Wikipedia search returns it."""
    return {
        "ns": 0,
        "title": title,
        "index": index,
        "description": "processo celular que guarda a energia da luz",
        "thumbnail": {"source": WIKI_THUMB, "width": 160, "height": 213},
        **data,
    }


# the plain text the API gives for an article: one paragraph per line, and
# headings marked like in the wiki source, with = signs for each level
ARTICLE_TEXT = """\
Fotossíntese é o processo pelo qual plantas, algas e algumas bactérias captam a energia da luz.
Quase todo o oxigênio livre da atmosfera tem essa origem.


== Visão geral ==


=== Etapas ===
A luz é absorvida pela clorofila.


== Fixação do carbono ==
O ciclo de Calvin fixa o carbono do CO2.


==== Fotorrespiração ====
A rubisco também reage com o oxigênio.


== Referências ==


== Ligações externas ==

Os cloroplastos e a fotossíntese, material da USP."""

WIKI_IMAGE = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/"
    "Aspen_tree_in_sunlight.jpg/960px-Aspen_tree_in_sunlight.jpg"
)
COMMONS_FILE = "https://commons.wikimedia.org/wiki/File:Aspen_tree_in_sunlight.jpg"


def wiki_article(title="Fotossíntese", extract=ARTICLE_TEXT, **data):
    """An article as the Wikipedia API returns it, with its plain text."""
    return {
        "pageid": 10962,
        "ns": 0,
        "title": title,
        "extract": extract,
        "pageimage": "Aspen_tree_in_sunlight.jpg",
        "description": "processo celular que guarda a energia da luz",
        "fullurl": "https://pt.wikipedia.org/wiki/" + quote(title.replace(" ", "_")),
        **data,
    }


def wiki_image(**metadata):
    """The information about an image, from Wikimedia Commons."""
    metadata = {
        "ImageDescription": {
            "en": "An aspen tree with sunlight shining through the leaves.",
            "pt": "Um <b>álamo</b> com o sol entre as folhas.",
            "_type": "lang",
        },
        "Artist": '<a href="//commons.wikimedia.org/wiki/User:BethGwynne">BethGwynne</a>',
        "LicenseShortName": "CC BY-SA 4.0",
        "LicenseUrl": "https://creativecommons.org/licenses/by-sa/4.0",
        **metadata,
    }
    return {
        "ns": 6,
        "title": "Ficheiro:Aspen tree in sunlight.jpg",
        "missing": True,  # the file lives on Commons, not on the Portuguese Wikipedia
        "known": True,
        "imagerepository": "shared",
        "imageinfo": [
            {
                "thumburl": WIKI_IMAGE,
                "thumbwidth": 800,
                "thumbheight": 1067,
                "descriptionurl": COMMONS_FILE,
                "extmetadata": {
                    name: {"value": value, "source": "commons-desc-page"}
                    for name, value in metadata.items()
                    if value is not None
                },
            }
        ],
    }


def wiki_api(
    *results, total=None, suggestion=None, article=None, image=None, redirected=None
):
    """A urlopen replacement that answers like the Wikipedia API.

    Searches get the results, File: titles get the image and any other title gets
    the article. A missing article or image is answered as a page that doesn't exist.
    """

    def urlopen(request, timeout):
        params = {
            k: v[0] for k, v in parse_qs(urlsplit(request.full_url).query).items()
        }
        if "gsrsearch" in params:
            searchinfo = {"totalhits": len(results) if total is None else total}
            if suggestion:
                searchinfo["suggestion"] = suggestion
            query = {"searchinfo": searchinfo}
            if results:  # with no results the API leaves "pages" out
                query["pages"] = list(results)
        else:
            title = params["titles"]
            page = image if title.startswith("File:") else article
            query = {"pages": [page or {"ns": 0, "title": title, "missing": True}]}
            if redirected and page:
                query["redirects"] = [{"from": redirected, "to": page["title"]}]
        body = {"batchcomplete": True, "query": query}
        return BytesIO(json.dumps(body).encode())

    return urlopen


class WikipediaApiMixin:
    def setUp(self):
        cache.clear()
        patcher = patch(WIKI_URLOPEN)
        self.urlopen = patcher.start()
        self.addCleanup(patcher.stop)
        self.answer(wiki_result())

    def answer(self, *results, **kwargs):
        kwargs.setdefault("article", wiki_article())
        kwargs.setdefault("image", wiki_image())
        self.urlopen.side_effect = wiki_api(*results, **kwargs)

    def requests(self):
        """The query string of each request to the Wikipedia API."""
        queries = []
        for call in self.urlopen.call_args_list:
            url = call.args[0].full_url
            self.assertTrue(url.startswith("https://pt.wikipedia.org/w/api.php?"))
            self.assertIn("timeout", call.kwargs)
            queries.append({k: v[0] for k, v in parse_qs(urlsplit(url).query).items()})
        return queries

    def requested(self):
        """The query string of the last request to the Wikipedia API."""
        return self.requests()[-1]


class WikipediaSearchTests(WikipediaApiMixin, TestCase):
    url = reverse("learning:wikipedia")

    def search(self, query):
        return self.client.get(f"{self.url}?{query}")

    def test_courses_page_links_to_the_wikipedia_page(self):
        response = self.client.get(reverse("learning:cursos"))

        self.assertContains(
            response,
            f'<a class="btn btn-primary btn-block" href="{self.url}">Acessar curso'
            '<span class="sr-only">: Wikipédia</span></a>',
            html=True,
        )

    def test_page_without_a_search_only_shows_the_form(self):
        response = self.client.get(self.url)

        self.urlopen.assert_not_called()
        self.assertContains(response, "<title>Wikipédia - iZone</title>")
        self.assertContains(response, '<label for="id_q">Assunto</label>')
        self.assertContains(response, 'aria-describedby="id_q_helptext"')
        self.assertContains(response, '<p class="field-hint" id="id_q_helptext">')
        self.assertNotContains(response, 'id="resultados-h"')

    def test_search_asks_wikipedia_in_portuguese_for_articles(self):
        response = self.search("q=fotossíntese")

        params = self.requested()
        self.assertEqual(params["generator"], "search")
        self.assertEqual(params["gsrsearch"], "fotossíntese")
        self.assertEqual(params["gsrnamespace"], "0")  # articles only
        self.assertEqual(params["gsrlimit"], "10")
        self.assertEqual(params["gsroffset"], "0")
        self.assertContains(
            response, "<title>fotossíntese, página 1 de 1 - Wikipédia - iZone</title>"
        )
        # after searching, the focus goes to the results
        self.assertContains(
            response,
            '<h2 id="resultados-h" tabindex="-1" autofocus>Resultados para “fotossíntese”</h2>',
        )
        self.assertContains(response, "1 artigo encontrado.")

    def test_requests_name_the_project(self):
        # Wikimedia asks every client for a User-Agent that says who it is
        self.search("q=fotossíntese")

        agent = self.urlopen.call_args.args[0].get_header("User-agent")
        self.assertIn("iZone", agent)
        self.assertIn("https://github.com/projetoizone/izone", agent)

    def test_results_link_to_the_article_with_its_description(self):
        response = self.search("q=fotossíntese")

        article = reverse("learning:wikipedia_artigo", args=["Fotossíntese"])
        self.assertContains(
            response,
            f'<h3><a href="{article}?q=fotoss%C3%ADntese">Fotossíntese</a></h3>',
            html=True,
        )
        self.assertContains(
            response, "<p>processo celular que guarda a energia da luz</p>", html=True
        )
        # the link already names the article, so the thumbnail is decorative
        self.assertContains(
            response, f'<img src="{WIKI_THUMB}" alt="" loading="lazy">', html=True
        )

    def test_titles_with_spaces_use_underscores_in_the_link(self):
        self.answer(wiki_result("Machado de Assis"))

        response = self.search("q=machado")

        self.assertContains(
            response, 'href="/learning/cursos/wikipedia/Machado_de_Assis?'
        )

    def test_results_keep_the_search_order(self):
        # the API lists the pages in any order, with their position in "index"
        self.answer(wiki_result("Clorofila", index=2), wiki_result("Fotossíntese"))

        html = self.search("q=fotossíntese").content.decode()

        self.assertLess(html.index(">Fotossíntese<"), html.index(">Clorofila<"))

    def test_suggests_a_spelling_that_finds_more(self):
        self.answer(wiki_result(), suggestion="fotossíntese")

        response = self.search("q=fotosintese")

        self.assertContains(
            response,
            f'<p>Você quis dizer <a href="{self.url}?q=fotoss%C3%ADntese">fotossíntese</a>?</p>',
            html=True,
        )

    def test_suggestion_equal_to_the_search_is_left_out(self):
        self.answer(wiki_result(), suggestion="Fotossíntese")

        response = self.search("q=fotossíntese")

        self.assertNotContains(response, "Você quis dizer")

    def test_invalid_search_shows_the_error_on_the_field(self):
        cases = {
            "q=": "Digite um assunto para pesquisar.",
            "q=" + "a" * 301: "Use no máximo 300 caracteres.",
        }
        for query, message in cases.items():
            with self.subTest(message=message):
                response = self.search(query)

                self.urlopen.assert_not_called()
                html = response.content.decode()
                self.assertIn("<title>Erro: Wikipédia - iZone</title>", html)
                self.assertIn(f'<p class="field-error" id="id_q_error">{message}', html)
                tag = re.search(r'<input [^>]*id="id_q"[^>]*>', html).group()
                self.assertIn('aria-invalid="true"', tag)
                self.assertIn("id_q_error", tag)
                self.assertIn("autofocus", tag)

    def test_pages_link_to_each_other_and_keep_the_search(self):
        self.answer(wiki_result(), total=30)  # 3 pages of 10

        response = self.search("q=brasil&pagina=2")

        self.assertEqual(self.requested()["gsroffset"], "10")
        self.assertContains(response, "30 artigos encontrados. Página 2 de 3.")
        self.assertContains(response, f'href="{self.url}?q=brasil" rel="prev"')
        self.assertContains(
            response, f'href="{self.url}?q=brasil&amp;pagina=3" rel="next"'
        )
        article = reverse("learning:wikipedia_artigo", args=["Fotossíntese"])
        self.assertContains(response, f'href="{article}?q=brasil&amp;pagina=2"')

    def test_page_number_stays_within_what_the_api_serves(self):
        # the API serves the first 10,000 results of a search
        for value, offset in (("abc", "0"), ("0", "0"), ("99999", "9990")):
            with self.subTest(pagina=value):
                self.search(f"q=brasil&pagina={value}")

                self.assertEqual(self.requested()["gsroffset"], offset)

    def test_page_past_the_last_one_links_back(self):
        self.answer(total=30)

        response = self.search("q=brasil&pagina=5")

        self.assertContains(response, "Esta pesquisa tem 3 páginas.")
        self.assertContains(
            response,
            f'<a href="{self.url}?q=brasil&amp;pagina=3">Ir para a última página</a>',
            html=True,
        )

    def test_no_results(self):
        self.answer(total=0)

        response = self.search("q=xqzjwvkq")

        self.assertContains(response, "Nenhum artigo encontrado.")

    def test_unusable_results_are_left_out(self):
        self.answer(
            wiki_result("Usuário(a):Teste", ns=2),
            wiki_result(""),
            wiki_result("Imagem perigosa", thumbnail={"source": "javascript:alert(1)"}),
            wiki_result("Fotossíntese", index=4),
        )

        response = self.search("q=teste")

        self.assertNotContains(response, "Usuário(a):Teste")
        self.assertNotContains(response, "javascript:")
        self.assertContains(response, "Imagem perigosa")  # shown, without the image
        self.assertContains(response, ">Fotossíntese<")

    def test_api_failures_show_a_message(self):
        api_error = {"error": {"code": "cirrussearch-backend-error", "info": "x"}}
        failures = {
            "offline": URLError("no network"),
            "timeout": TimeoutError(),
            "server error": HTTPError("u", 500, "Error", {}, BytesIO(b"")),
            "too many requests": HTTPError("u", 429, "Too Many", {}, BytesIO(b"")),
            "not json": lambda request, timeout: BytesIO(b"<html>"),
            "api error": lambda request, timeout: BytesIO(
                json.dumps(api_error).encode()
            ),
            "no query": lambda request, timeout: BytesIO(b"[]"),
        }
        for case, failure in failures.items():
            with self.subTest(case=case):
                cache.clear()
                self.urlopen.side_effect = failure

                response = self.search("q=brasil")

                self.assertContains(response, "Pesquisa não concluída", status_code=502)
                self.assertContains(response, wikipedia.UNAVAILABLE, status_code=502)

    def test_results_are_cached(self):
        self.search("q=brasil")
        self.search("q=brasil")
        self.search("q=portugal")

        self.assertEqual(self.urlopen.call_count, 2)


class WikipediaArticleTests(WikipediaApiMixin, TestCase):
    def read(self, title="Fotossíntese", query=""):
        url = reverse("learning:wikipedia_artigo", args=[title])
        return self.client.get(f"{url}?{query}" if query else url)

    def test_asks_for_the_article_as_plain_text(self):
        self.read()

        article = self.requests()[0]
        self.assertEqual(article["titles"], "Fotossíntese")
        self.assertIn("extracts", article["prop"].split("|"))
        self.assertEqual(article["explaintext"], "1")
        self.assertEqual(article["exsectionformat"], "wiki")
        self.assertEqual(article["redirects"], "1")

    def test_shows_the_title_and_the_short_description(self):
        response = self.read()

        self.assertContains(response, "<title>Fotossíntese - Wikipédia - iZone</title>")
        self.assertContains(
            response, '<h1 class="page-title">Fotossíntese</h1>', html=True
        )
        self.assertContains(
            response,
            '<p class="lede">processo celular que guarda a energia da luz</p>',
            html=True,
        )

    def test_text_is_split_into_paragraphs_and_sections(self):
        response = self.read()

        for paragraph in (
            (
                "Fotossíntese é o processo pelo qual plantas, algas e algumas "
                "bactérias captam a energia da luz."
            ),
            "Quase todo o oxigênio livre da atmosfera tem essa origem.",
            "A luz é absorvida pela clorofila.",
        ):
            with self.subTest(paragraph=paragraph):
                self.assertContains(response, f"<p>{paragraph}</p>", html=True)
        self.assertContains(response, '<h2 id="secao-1">Visão geral</h2>', html=True)
        self.assertContains(response, '<h3 id="secao-2">Etapas</h3>', html=True)
        html = response.content.decode()
        self.assertNotIn("==", html[html.index("<main") : html.index("</main>")])

    def test_sections_without_text_are_left_out(self):
        response = self.read()

        self.assertNotContains(response, "Referências")
        # a section with only subsections stays
        self.assertContains(response, "Visão geral")

    def test_heading_levels_never_skip(self):
        # "==== Fotorrespiração ====" comes right after a level 2 section
        response = self.read()

        self.assertContains(
            response, '<h3 id="secao-4">Fotorrespiração</h3>', html=True
        )

    def test_contents_list_links_to_each_section(self):
        html = self.read().content.decode()

        nav = re.search(
            r'<nav class="wiki-contents" aria-labelledby="neste-artigo-h">.*?</nav>',
            html,
            flags=re.DOTALL,
        ).group()
        self.assertIn('<h2 id="neste-artigo-h">Neste artigo</h2>', nav)
        self.assertEqual(
            re.findall(r'<a href="#(secao-\d+)">([^<]+)</a>', nav),
            [
                ("secao-1", "Visão geral"),
                ("secao-3", "Fixação do carbono"),
                ("secao-5", "Ligações externas"),
            ],
        )

    def test_text_from_the_api_is_escaped(self):
        self.answer(article=wiki_article(extract="Use <script>alert(1)</script> aqui."))

        response = self.read()

        self.assertNotContains(response, "<script>alert(1)")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_asks_commons_about_the_main_image(self):
        self.read()

        image = self.requested()
        self.assertEqual(image["titles"], "File:Aspen_tree_in_sunlight.jpg")
        self.assertEqual(image["prop"], "imageinfo")
        self.assertEqual(set(image["iiprop"].split("|")), {"url", "extmetadata"})
        self.assertEqual(image["iiurlwidth"], "800")
        self.assertEqual(image["iiextmetadatamultilang"], "1")

    def test_main_image_is_described_and_credited(self):
        response = self.read()

        # the description from Commons, in Portuguese when there is one
        self.assertContains(
            response,
            f'<img src="{WIKI_IMAGE}" width="800" height="1067" '
            'alt="Um álamo com o sol entre as folhas.">',
            html=True,
        )
        # the image license asks for the author and the license
        self.assertContains(
            response,
            "<figcaption>Imagem: BethGwynne, licença "
            '<a href="https://creativecommons.org/licenses/by-sa/4.0">CC BY-SA 4.0</a>. '
            f'<a href="{COMMONS_FILE}">Ver a imagem no Wikimedia Commons</a></figcaption>',
            html=True,
        )

    def test_description_in_another_language_is_marked(self):
        description = {"en": "An aspen tree in the sun.", "_type": "lang"}
        self.answer(image=wiki_image(ImageDescription=description))

        response = self.read()

        self.assertContains(response, 'alt="An aspen tree in the sun." lang="en"')

    def test_image_without_a_description_is_named_after_the_article(self):
        self.answer(image=wiki_image(ImageDescription=None))

        response = self.read()

        self.assertContains(response, 'alt="Imagem do artigo Fotossíntese"')

    def test_public_domain_image(self):
        self.answer(image=wiki_image(LicenseShortName="Public domain", LicenseUrl=None))

        response = self.read()

        self.assertContains(response, "Imagem: BethGwynne, domínio público.")

    def test_article_without_an_image(self):
        self.answer(article=wiki_article(pageimage=None))

        response = self.read()

        self.assertEqual(self.urlopen.call_count, 1)
        self.assertNotContains(response, "<figure")

    def test_unusable_image_is_left_out(self):
        unsafe = wiki_image()
        unsafe["imageinfo"][0]["thumburl"] = "javascript:alert(1)"
        for case, image in {"not on Commons": None, "unsafe address": unsafe}.items():
            with self.subTest(case=case):
                cache.clear()
                self.answer(image=image)

                response = self.read()

                self.assertNotContains(response, "<figure")
                self.assertNotContains(response, "javascript:")
                self.assertContains(response, "A luz é absorvida pela clorofila.")

    def test_article_is_shown_even_if_the_image_fails(self):
        answer = self.urlopen.side_effect

        def image_fails(request, timeout):
            if "File%3A" in request.full_url:
                raise URLError("no network")
            return answer(request, timeout)

        self.urlopen.side_effect = image_fails

        response = self.read()

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<figure")
        self.assertContains(response, "A luz é absorvida pela clorofila.")

    def test_disambiguation_page_leads_to_a_search(self):
        # the page lists articles with similar names, but plain text has no links
        self.answer(
            article=wiki_article(
                "Mercúrio",
                extract="Mercúrio pode referir-se a:\nMercúrio (planeta) — o menor planeta",
                pageimage=None,
                pageprops={"disambiguation": ""},
            )
        )

        response = self.read("Mercúrio")

        self.assertIn("pageprops", self.requested()["prop"].split("|"))
        search = reverse("learning:wikipedia")
        self.assertContains(
            response,
            "<p>Esta página lista artigos com nomes parecidos. Para abrir um deles, "
            f'<a href="{search}?q=Merc%C3%BArio">pesquise “Mercúrio”</a>.</p>',
            html=True,
        )

    def test_other_articles_do_not_suggest_a_search(self):
        response = self.read()

        self.assertNotContains(response, "Esta página lista artigos")

    def test_says_where_the_text_comes_from(self):
        response = self.read()

        self.assertContains(
            response,
            '<a href="https://pt.wikipedia.org/wiki/Fotoss%C3%ADntese">'
            "Ler este artigo na Wikipédia</a>",
            html=True,
        )
        # the text license asks for the source, the authors and the license
        self.assertContains(
            response,
            'href="https://pt.wikipedia.org/w/index.php?title=Fot'
            'oss%C3%ADntese&amp;action=history"',
        )
        self.assertContains(
            response,
            '<a href="https://creativecommons.org/licenses/by-sa/4.0/deed.pt_BR">'
            "licença CC BY-SA 4.0</a>",
            html=True,
        )
        # plain text leaves out what can't be written as text
        self.assertContains(response, "Fórmulas, tabelas e quadros não aparecem")

    def test_other_names_lead_to_the_article(self):
        cases = {
            "EUA": ("Estados Unidos", "Estados_Unidos"),  # a redirect
            "fotossíntese": ("Fotossíntese", "Fotoss%C3%ADntese"),  # first letter
            "Machado de Assis": ("Machado de Assis", "Machado_de_Assis"),  # spaces
        }
        for asked, (title, slug) in cases.items():
            with self.subTest(asked=asked):
                cache.clear()
                self.answer(article=wiki_article(title), redirected=asked)

                response = self.read(asked, query="q=eua")

                self.assertRedirects(
                    response,
                    f"/learning/cursos/wikipedia/{slug}?q=eua",
                    fetch_redirect_response=False,
                )

    def test_unknown_article_is_not_found(self):
        for article in (None, {"title": "[x]", "invalid": True}, wiki_article(ns=2)):
            with self.subTest(article=article):
                cache.clear()
                self.answer(article=article)

                response = self.read()

                self.assertContains(response, "Artigo não encontrado", status_code=404)

    def test_api_failure_shows_a_message(self):
        self.urlopen.side_effect = URLError("no network")

        response = self.read()

        self.assertContains(response, "Artigo indisponível", status_code=502)
        self.assertContains(response, wikipedia.UNAVAILABLE, status_code=502)

    def test_back_link_returns_to_the_results(self):
        search = reverse("learning:wikipedia")

        from_results = self.read(query="q=fotoss%C3%ADntese&pagina=2")
        direct = self.read()

        self.assertContains(
            from_results,
            f'<a href="{search}?q=fotoss%C3%ADntese&amp;pagina=2">Voltar aos resultados</a>',
            html=True,
        )
        self.assertContains(
            direct, f'<a href="{search}">Pesquisar na Wikipédia</a>', html=True
        )

    def test_article_is_cached(self):
        self.read()
        self.read()

        self.assertEqual(self.urlopen.call_count, 2)  # the article and its image

    def test_accessibility_page_documents_it(self):
        response = self.client.get(reverse("learning:acessibilidade"))

        self.assertContains(response, "Nos artigos da Wikipédia")


class ReadAloudLanguageTests(TestCase):
    def test_each_passage_is_read_in_its_own_language(self):
        js = (settings.BASE_DIR / "public" / "js" / "accessibility.js").read_text()

        self.assertIn('closest("[lang]")', js)
        self.assertNotIn('current.lang = "pt-BR"', js)

    def test_accessibility_page_documents_it(self):
        response = self.client.get(reverse("learning:acessibilidade"))

        self.assertContains(response, "Trechos em inglês")
        self.assertContains(response, "As imagens têm texto alternativo.")
