import json
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from opspilot.monitor import Check, check_endpoint, load_checks


class LoadChecksTests(unittest.TestCase):
    def load_config(self, value):
        temporary_file = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        )
        self.addCleanup(Path(temporary_file.name).unlink, missing_ok=True)
        with temporary_file:
            json.dump(value, temporary_file)
        return load_checks(temporary_file.name)

    def test_loads_valid_checks_and_default_timeout(self):
        checks = self.load_config(
            {"checks": [{"name": "api", "url": "https://example.com/health"}]}
        )

        self.assertEqual(checks, [Check("api", "https://example.com/health", 5.0)])

    def test_rejects_empty_checks(self):
        with self.assertRaisesRegex(ValueError, "at least one endpoint"):
            self.load_config({"checks": []})

    def test_rejects_non_http_urls(self):
        with self.assertRaisesRegex(ValueError, "valid http or https URL"):
            self.load_config({"checks": [{"name": "api", "url": "file:///etc/passwd"}]})

    def test_rejects_malformed_http_urls(self):
        with self.assertRaisesRegex(ValueError, "valid http or https URL"):
            self.load_config({"checks": [{"name": "api", "url": "http://[invalid"}]})

    def test_rejects_invalid_port(self):
        with self.assertRaisesRegex(ValueError, "valid http or https URL"):
            self.load_config(
                {"checks": [{"name": "api", "url": "http://example.com:invalid"}]}
            )

    def test_rejects_credentials_in_url(self):
        with self.assertRaisesRegex(ValueError, "valid http or https URL"):
            self.load_config(
                {
                    "checks": [
                        {
                            "name": "api",
                            "url": "https://user:password@example.com/health",
                        }
                    ]
                }
            )

    def test_rejects_whitespace_in_url(self):
        with self.assertRaisesRegex(ValueError, "valid http or https URL"):
            self.load_config(
                {"checks": [{"name": "api", "url": "https://example.com/health path"}]}
            )

    def test_rejects_boolean_timeout(self):
        with self.assertRaisesRegex(ValueError, "positive number"):
            self.load_config(
                {
                    "checks": [
                        {
                            "name": "api",
                            "url": "https://example.com",
                            "timeout_seconds": True,
                        }
                    ]
                }
            )

    def test_rejects_infinite_timeout(self):
        with self.assertRaisesRegex(ValueError, "positive number"):
            self.load_config(
                {
                    "checks": [
                        {
                            "name": "api",
                            "url": "https://example.com",
                            "timeout_seconds": float("inf"),
                        }
                    ]
                }
            )

    def test_rejects_duplicate_names(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            self.load_config(
                {
                    "checks": [
                        {"name": "api", "url": "https://example.com"},
                        {"name": "api", "url": "https://example.org"},
                    ]
                }
            )


class CheckEndpointTests(unittest.TestCase):
    @patch("opspilot.monitor.urlopen")
    def test_reports_successful_response(self, mock_urlopen):
        response = mock_urlopen.return_value.__enter__.return_value
        response.getcode.return_value = 204

        result = check_endpoint(Check("api", "https://example.com"))

        self.assertTrue(result.healthy)
        self.assertEqual(result.status_code, 204)
        self.assertIsNone(result.error)

    @patch("opspilot.monitor.urlopen")
    def test_reports_http_error_status(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://example.com", 503, "Unavailable", {}, BytesIO()
        )

        result = check_endpoint(Check("api", "https://example.com"))

        self.assertFalse(result.healthy)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.error, "HTTP 503")

    @patch("opspilot.monitor.urlopen", side_effect=URLError("connection refused"))
    def test_reports_connection_error(self, _mock_urlopen):
        result = check_endpoint(Check("api", "https://example.com"))

        self.assertFalse(result.healthy)
        self.assertIsNone(result.status_code)
        self.assertEqual(result.error, "connection refused")


if __name__ == "__main__":
    unittest.main()
