import itertools
import re
from html.parser import HTMLParser

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()
PASSWORD = "Senha-forte-123"

# pages that use the shared layout and can be opened without logging in
PAGES = (
    "learning:home",
    "learning:cursos",
    "learning:tutoriais",
    "learning:comunidade",
    "learning:acessibilidade",
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


def strip_tags(html):
    html = re.sub(
        r'<(\w+)[^>]*aria-hidden="true"[^>]*>.*?</\1>', "", html, flags=re.DOTALL
    )
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


class ScreenReaderStructureTests(TestCase):
    def pages(self):
        for name in PAGES:
            yield name, self.client.get(reverse(name)).content.decode()
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


def css_themes():
    """The custom properties of each theme in style.css, with var() resolved."""
    css = (settings.BASE_DIR / "public" / "css" / "style.css").read_text()
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
        css = (settings.BASE_DIR / "public" / "css" / "style.css").read_text()
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
