import io
from contextlib import redirect_stdout
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from packages.core.runtime.console_human_interaction import (
    ConsoleHumanInteraction,
    HumanInputUnavailable,
)


class TestConsoleHumanInteraction(IsolatedAsyncioTestCase):
    async def test_approval_requires_exact_approval(self):
        interaction = ConsoleHumanInteraction()

        with patch("builtins.input", return_value="approve"):
            self.assertTrue(
                await interaction.request_approval(
                    "open_application",
                    "high",
                    {"application": "chrome"},
                    "local-user",
                )
            )

        with patch("builtins.input", return_value="yes"):
            self.assertFalse(
                await interaction.request_approval(
                    "open_application",
                    "high",
                    {"application": "chrome"},
                    "local-user",
                )
            )

    async def test_unavailable_approval_input_denies(self):
        interaction = ConsoleHumanInteraction()

        with patch("builtins.input", side_effect=EOFError):
            approved = await interaction.request_approval(
                "open_application",
                "high",
                {"application": "chrome"},
                "local-user",
            )

        self.assertFalse(approved)

    async def test_approval_display_redacts_sensitive_arguments(self):
        interaction = ConsoleHumanInteraction()
        output = io.StringIO()

        with (
            patch("builtins.input", return_value="deny"),
            redirect_stdout(output),
        ):
            approved = await interaction.request_approval(
                "open_application",
                "high",
                {
                    "application": "chrome",
                    "api_key": "do-not-display",
                },
                "local-user",
            )

        self.assertFalse(approved)
        self.assertNotIn("do-not-display", output.getvalue())
        self.assertIn("[REDACTED]", output.getvalue())

    async def test_approval_display_redacts_url_credentials(self):
        interaction = ConsoleHumanInteraction()
        output = io.StringIO()

        with (
            patch("builtins.input", return_value="deny"),
            redirect_stdout(output),
        ):
            await interaction.request_approval(
                "open_application",
                "high",
                {"url": "https://user:password@example.com/?api_key=secret-value"},
                "local-user",
            )

        rendered = output.getvalue()
        self.assertNotIn("user:password", rendered)
        self.assertNotIn("secret-value", rendered)

    async def test_clarification_accepts_listed_option(self):
        interaction = ConsoleHumanInteraction()

        with patch("builtins.input", return_value="2"):
            answer = await interaction.ask_clarification(
                "Which browser should I open?",
                ("Chrome", "Edge"),
            )

        self.assertEqual(answer, "Edge")

    async def test_clarification_retries_invalid_choice(self):
        interaction = ConsoleHumanInteraction()

        with patch("builtins.input", side_effect=["Firefox", "1"]):
            answer = await interaction.ask_clarification(
                "Choose a browser.",
                ("Chrome", "Edge"),
            )

        self.assertEqual(answer, "Chrome")

    async def test_clarification_reports_unavailable_input(self):
        interaction = ConsoleHumanInteraction()

        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(HumanInputUnavailable):
                await interaction.ask_clarification("What should I open?")
