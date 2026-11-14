import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from opspilot.api import create_app
from opspilot.monitor import CheckResult


class ApiTests(unittest.TestCase):
    def create_config(self):
        config_file = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        )
        self.addCleanup(Path(config_file.name).unlink, missing_ok=True)
        with config_file:
            json.dump(
                {
                    "checks": [
                        {
                            "name": "api",
                            "url": "https://example.com/health",
                        }
                    ]
                },
                config_file,
            )
        return config_file.name

    def test_api_checks_and_prometheus_metrics(self):
        check_result = CheckResult(
            name="api",
            url="https://example.com/health",
            healthy=True,
            status_code=200,
            latency_ms=8.5,
        )
        with patch("opspilot.api.check_endpoint", return_value=check_result):
            with TestClient(
                create_app(self.create_config(), interval_seconds=3600)
            ) as client:
                root_response = client.get("/", follow_redirects=False)
                favicon_response = client.get("/favicon.ico")
                self.assertEqual(client.get("/healthz").json(), {"status": "ok"})
                self.assertEqual(client.get("/readyz").status_code, 200)
                self.assertEqual(
                    client.get("/api/v1/checks").json()["checks"][0]["name"],
                    "api",
                )

                run_response = client.post("/api/v1/checks/run")
                metrics_response = client.get("/metrics")

        self.assertEqual(root_response.status_code, 307)
        self.assertEqual(root_response.headers["location"], "/docs")
        self.assertEqual(favicon_response.status_code, 204)
        self.assertTrue(run_response.json()["healthy"])
        self.assertEqual(run_response.json()["results"][0]["status_code"], 200)
        self.assertIn(
            'opspilot_check_success{check_name="api"} 1.0',
            metrics_response.text,
        )

    def test_rejects_non_positive_schedule_interval(self):
        with self.assertRaisesRegex(ValueError, "positive finite number"):
            create_app(self.create_config(), interval_seconds=0)


if __name__ == "__main__":
    unittest.main()
