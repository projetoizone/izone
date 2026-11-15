import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()
PASSWORD = "Senha-forte-123"


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
        pages = [
            "learning:home",
            "learning:cursos",
            "learning:tutoriais",
            "learning:comunidade",
            "learning:acessibilidade",
            "accounts:login",
            "accounts:signup",
            "spelling:game",
        ]
        for name in pages:
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
