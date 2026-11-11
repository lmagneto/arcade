from django.test import SimpleTestCase


class HealthCheckTests(SimpleTestCase):
    def test_health_endpoint_is_public_and_returns_minimal_response(self):
        response = self.client.get("/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        self.assertEqual(response["Content-Type"], "text/plain")

    def test_health_endpoint_does_not_accept_other_methods(self):
        response = self.client.post("/health/")

        self.assertEqual(response.status_code, 405)
