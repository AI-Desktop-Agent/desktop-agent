
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from packages.security.audit import AuditLog, MAX_ENTRY_CHARS


class TestAuditLog(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "audit.jsonl"

        self.audit = AuditLog(
            path=self.path,
            clock=lambda: datetime(2026, 11, 8, tzinfo=timezone.utc)
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_entry(self, **overrides):
        data = {
            "call_id": "call-123",
            "tool": "send_email",
            "principal": "user-1",
            "risk": "high",
            "outcome": "allowed",
            "args": {"to": "test@example.com"},
            "detail": "Email approved"
        }
        data.update(overrides)
        self.audit.write(**data)

    # Basic behavior

    def test_write_and_read_entry(self):
        self.write_entry()

        entries = self.audit.read()

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["tool"], "send_email")
        self.assertEqual(entries[0]["outcome"], "allowed")

    def test_timestamp_is_utc(self):
        self.write_entry()

        entry = self.audit.read()[0]

        self.assertTrue(entry["ts"].endswith("+00:00"))

    def test_invalid_outcome_is_rejected(self):
        with self.assertRaises(ValueError):
            self.write_entry(outcome="unknown")

    # Redaction

    def test_password_key_is_redacted(self):
        self.write_entry(
            args={"password": "my-secret-password"}
        )

        entry = self.audit.read()[0]

        self.assertEqual(
            entry["args"]["password"],
            "[REDACTED]"
        )

    def test_nested_token_is_redacted(self):
        self.write_entry(
            args={
                "config": {
                    "api_key": "secret-value"
                }
            }
        )

        entry = self.audit.read()[0]

        self.assertEqual(
            entry["args"]["config"]["api_key"],
            "[REDACTED]"
        )

    def test_secret_in_detail_is_redacted(self):
        self.write_entry(
            detail="Request failed with Bearer abcdefghijklmnop"
        )

        entry = self.audit.read()[0]

        self.assertNotIn("abcdefghijklmnop", entry["detail"])
        self.assertIn("[REDACTED]", entry["detail"])

    # Size limit

    def test_entry_never_exceeds_maximum_size(self):
        self.write_entry(
            args={"message": "x" * 100000},
            detail="large detail " * 1000
        )

        for line in self.path.read_text(encoding="utf-8").splitlines():
            self.assertLessEqual(
                len(line),
                MAX_ENTRY_CHARS
            )

    def test_oversized_entry_is_rejected_before_write(self):
        # Force a small limit to verify the guard itself.
        with patch("packages.security.audit.MAX_ENTRY_CHARS", 10):
            with self.assertRaises(ValueError):
                self.write_entry()

        self.assertFalse(self.path.exists())

    # File permissions

    @unittest.skipUnless(os.name == "posix", "POSIX permissions only")
    def test_existing_file_permissions_are_restricted(self):
        self.path.write_text("", encoding="utf-8")
        os.chmod(self.path, 0o644)

        self.write_entry()

        permissions = self.path.stat().st_mode & 0o777

        self.assertEqual(permissions, 0o600)

    # Recovery

    def test_missing_file_returns_empty_list(self):
        self.assertEqual(self.audit.read(), [])

    def test_damaged_final_line_is_ignored_in_normal_mode(self):
        self.write_entry()

        with open(self.path, "a", encoding="utf-8") as f:
            f.write('{"damaged":')

        self.assertEqual(len(self.audit.read()), 1)

    def test_damaged_final_line_raises_in_strict_mode(self):
        self.write_entry()

        with open(self.path, "a", encoding="utf-8") as f:
            f.write('{"damaged":')

        with self.assertRaises(json.JSONDecodeError):
            self.audit.read(strict=True)

    def test_damaged_middle_line_raises(self):
        self.write_entry()

        with open(self.path, "a", encoding="utf-8") as f:
            f.write('{"damaged":}\n')
            f.write('{"valid": true}\n')

        with self.assertRaises(json.JSONDecodeError):
            self.audit.read()


if __name__ == "__main__":
    unittest.main()
