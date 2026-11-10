from django.contrib.auth import get_user_model
from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import TestCase


class AdminThemeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.admin_user = user_model.objects.create_superuser(
            username="admin-theme-test",
            email="admin-theme-test@example.com",
            password="test-password",
        )

    def test_login_page_loads_custom_admin_stylesheet(self):
        response = self.client.get("/admin/login/")
        stylesheet_url = staticfiles_storage.url(
            "admin/css/arcade_admin.css"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, stylesheet_url)
        self.assertContains(response, "ARCADE")

        stylesheet_response = self.client.get(stylesheet_url)

        self.assertEqual(stylesheet_response.status_code, 200)
        self.assertTrue(
            stylesheet_response["Content-Type"].startswith("text/css")
        )

    def test_dashboard_uses_arcade_branding_and_operations_header(self):
        self.client.force_login(self.admin_user)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ARCADE")
        self.assertContains(response, "Operations dashboard")
        self.assertContains(response, "PLATFORM OPERATIONS")
        self.assertContains(
            response,
            staticfiles_storage.url("admin/css/arcade_admin.css"),
        )
