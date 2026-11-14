import contextlib
import io
import json
import unittest
from unittest.mock import patch

from opspilot.cli import main
from opspilot.monitor import Check, CheckResult


class CliTests(unittest.TestCase):
    @patch("opspilot.cli.check_endpoint")
    @patch("opspilot.cli.load_checks", return_value=[Check("api", "https://example.com")])
    def test_json_output_and_unhealthy_exit_code(self, _load_checks, check):
        check.return_value = CheckResult(
            name="api",
            url="https://example.com",
            healthy=False,
            status_code=503,
            latency_ms=12.5,
            error="HTTP 503",
        )
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = main(["--config", "unused.json", "--json"])

        result = json.loads(output.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(result["healthy"])
        self.assertEqual(result["results"][0]["status_code"], 503)

    @patch("opspilot.cli.load_checks", side_effect=ValueError("invalid config"))
    def test_invalid_config_returns_configuration_exit_code(self, _load_checks):
        errors = io.StringIO()

        with contextlib.redirect_stderr(errors):
            exit_code = main(["--config", "unused.json"])

        self.assertEqual(exit_code, 2)
        self.assertIn("invalid config", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
