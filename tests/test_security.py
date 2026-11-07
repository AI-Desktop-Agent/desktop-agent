import unittest
from dataclasses import FrozenInstanceError

from langchain_core.tools import tool

from packages.security.registry import REGISTRY, get_tools, secure_tool


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self._saved = dict(REGISTRY)
        REGISTRY.clear()

    def tearDown(self):
        REGISTRY.clear()
        REGISTRY.update(self._saved)

    def test_registers_tool_with_its_settings(self):
        @secure_tool(risk="high", external=True, scopes=["mail.send"])
        @tool("send_x")
        def send_x(to: str) -> str:
            """Send something."""
            return "sent"

        spec = REGISTRY["send_x"]
        self.assertEqual(spec.risk, "high")
        self.assertTrue(spec.external)
        self.assertFalse(spec.taints)
        self.assertEqual(spec.scopes, frozenset({"mail.send"}))

    def test_default_risk_is_high(self):
        @secure_tool()
        @tool("no_risk_given")
        def f() -> str:
            """Do something."""
            return "x"

        self.assertEqual(REGISTRY["no_risk_given"].risk, "high")

    def test_risk_can_be_a_function(self):
        def risk(args):
            return "low"

        @secure_tool(risk=risk)
        @tool("computed")
        def f(x: str) -> str:
            """Do something."""
            return x

        self.assertIs(REGISTRY["computed"].risk, risk)

    def test_unknown_tier_is_rejected_immediately(self):
        with self.assertRaises(ValueError):
            secure_tool(risk="hihg")

    def test_wrong_decorator_order_is_rejected(self):
        with self.assertRaises(TypeError):
            secure_tool("low")(lambda: None)

    def test_duplicate_name_is_rejected(self):
        @secure_tool("low")
        @tool("dup")
        def a() -> str:
            """First."""
            return "a"

        with self.assertRaises(ValueError):
            @secure_tool("low")
            @tool("dup")
            def b() -> str:
                """Second."""
                return "b"

    def test_get_tools_returns_the_tool_objects(self):
        @secure_tool("low")
        @tool("listed")
        def f() -> str:
            """Do something."""
            return "x"

        self.assertEqual([t.name for t in get_tools()], ["listed"])

    def test_spec_is_read_only(self):
        @secure_tool("low")
        @tool("frozen_one")
        def f() -> str:
            """Do something."""
            return "x"

        with self.assertRaises(FrozenInstanceError):
            REGISTRY["frozen_one"].risk = "high"

    def test_scopes_must_not_be_a_plain_string(self):
        with self.assertRaises(TypeError):
            secure_tool("low", scopes="mail.send")


if __name__ == "__main__":
    unittest.main()