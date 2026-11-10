import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from api import diagnostics


class DiagnosticsTests(unittest.TestCase):
    def test_checks_validate_provider_response_without_modifying_data(self):
        engine = MagicMock()
        engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = (
            "PostGIS test version"
        )
        client = MagicMock()
        client.return_value.__enter__.return_value.get.return_value.json.return_value = {
            "hourly": {"time": ["2026-11-10T00:00"], "precipitation": [1]}
        }
        with patch.object(diagnostics, "engine", engine), patch.object(
            diagnostics.httpx, "Client", client
        ):
            result = diagnostics.check_services()
        self.assertTrue(result["database"]["ok"])
        self.assertTrue(result["weather"]["ok"])
        self.assertFalse(result["model"]["required"])
        self.assertTrue(client.call_args.kwargs["verify"])
        self.assertEqual(
            str(
                engine.connect.return_value.__enter__.return_value.execute.call_args.args[
                    0
                ]
            ),
            "SELECT PostGIS_Version()",
        )

    def test_failures_are_reported_without_credentials_or_false_readiness(self):
        engine = MagicMock()
        engine.connect.side_effect = RuntimeError("sensitive-connection-details")
        client = MagicMock()
        client.return_value.__enter__.return_value.get.side_effect = RuntimeError(
            "sensitive-provider-details"
        )
        with patch.object(diagnostics, "engine", engine), patch.object(
            diagnostics.httpx, "Client", client
        ):
            result = diagnostics.check_services()
        self.assertFalse(result["database"]["ok"])
        self.assertFalse(result["weather"]["ok"])
        self.assertNotIn("sensitive-", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
