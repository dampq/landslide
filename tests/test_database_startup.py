"""Database readiness must exercise SQL through the application's connection path."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy.exc import OperationalError
from api import db


class DatabaseStartupTests(unittest.TestCase):
    def test_transient_connection_failures_are_retried_until_sql_succeeds(self):
        probe = MagicMock()
        connection = MagicMock()
        probe.connect.side_effect = [
            OperationalError("SELECT 1", None, Exception("initializing")),
            OperationalError("SELECT 1", None, Exception("restarting")),
            connection,
        ]
        with patch.object(
            db, "create_engine", return_value=probe
        ) as factory, patch.object(db.time, "sleep") as sleep, patch.object(
            db.time, "monotonic", return_value=0
        ):
            db.wait_for_database()
        self.assertEqual(probe.connect.call_count, 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(
            str(connection.__enter__.return_value.execute.call_args.args[0]), "SELECT 1"
        )
        self.assertEqual(factory.call_args.args[0], db.DATABASE_URL)
        self.assertEqual(factory.call_args.kwargs["connect_args"]["connect_timeout"], 3)
        probe.dispose.assert_called_once()

    def test_timeout_is_bounded_sanitized_and_disposes_connections(self):
        probe = MagicMock()
        probe.connect.side_effect = OperationalError(
            None, None, Exception("private connection details")
        )
        with patch.object(db, "create_engine", return_value=probe), patch.object(
            db.time, "monotonic", side_effect=[0, 61]
        ), patch.object(db.time, "sleep") as sleep:
            with self.assertRaisesRegex(
                RuntimeError, "Do not delete the database volume"
            ) as result:
                db.wait_for_database()
        self.assertNotIn("private connection details", str(result.exception))
        sleep.assert_not_called()
        probe.dispose.assert_called_once()


if __name__ == "__main__":
    unittest.main()
