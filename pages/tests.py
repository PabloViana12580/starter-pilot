from django.test import TestCase
from django.urls import reverse


class WebsitePageTests(TestCase):
    def test_public_pages_render_with_site_identity(self):
        for name in ('home', 'about', 'privacy', 'terms'):
            with self.subTest(page=name):
                response = self.client.get(reverse(f'pages:{name}'))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, response.context['site_info']['name'])

    def test_home_is_the_site_root(self):
        self.assertEqual(reverse('pages:home'), '/')

    def test_footer_links_to_legal_pages(self):
        response = self.client.get(reverse('pages:home'))
        self.assertContains(response, f'href="{reverse("pages:privacy")}"')
        self.assertContains(response, f'href="{reverse("pages:terms")}"')

    def test_pages_only_accept_get(self):
        self.assertEqual(self.client.post(reverse('pages:home')).status_code, 405)
