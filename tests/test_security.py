
import unittest
from unittest.mock import patch

from packages.security.gateway import ToolGateway
from packages.security.policy import Denied, POLICIES
from packages.security.registry import ToolSpec


class FakeTool:
    def __init__(self, name="fake_tool", result="success", error=None):
        self.name = name
        self.result = result
        self.error = error
        self.calls = 0

    async def ainvoke(self, args):
        self.calls += 1

        if self.error:
            raise self.error

        return self.result


class FakeRateLimiter:
    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def acquire(self, principal, tool, limit):
        self.calls.append((principal, tool, limit))

        if self.error:
            raise self.error


class FakeAudit:
    def __init__(self, fail_on=None):
        self.entries = []
        self.fail_on = fail_on

    def write(self, **entry):
        if entry["outcome"] == self.fail_on:
            raise OSError("Simulated audit failure")

        self.entries.append(entry)


class TestToolGateway(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.tool = FakeTool()

        self.registry = {
            "fake_tool": ToolSpec(
                tool=self.tool,
                risk="low",
                scopes=frozenset(),
            )
        }

        self.rate_limiter = FakeRateLimiter()
        self.audit = FakeAudit()

        self.gateway = ToolGateway(
            registry=self.registry,
            rate_limiter=self.rate_limiter,
            audit=self.audit,
        )

    # ---------------- Basic execution ----------------

    async def test_executes_registered_tool(self):
        result = await self.gateway.execute(
            "fake_tool",
            {"query": "hello"},
            principal="user-1",
        )

        self.assertEqual(result, "success")
        self.assertEqual(self.tool.calls, 1)

    async def test_unregistered_tool_is_denied(self):
        with self.assertRaises(Denied):
            await self.gateway.execute(
                "unknown_tool",
                {},
                principal="user-1",
            )

        self.assertEqual(self.tool.calls, 0)
        self.assertEqual(self.audit.entries[-1]["outcome"], "blocked")

    async def test_successful_execution_has_two_audit_events(self):
        await self.gateway.execute(
            "fake_tool",
            {},
            principal="user-1",
        )

        outcomes = [entry["outcome"] for entry in self.audit.entries]

        self.assertEqual(outcomes, ["allowed", "ok"])

        self.assertEqual(
            self.audit.entries[0]["call_id"],
            self.audit.entries[1]["call_id"],
        )

    # ---------------- Risk and policy ----------------

    async def test_blocked_risk_is_denied(self):
        self.registry["fake_tool"] = ToolSpec(
            tool=self.tool,
            risk="blocked",
        )

        with self.assertRaises(Denied):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
            )

        self.assertEqual(self.tool.calls, 0)
        self.assertEqual(self.audit.entries[-1]["outcome"], "blocked")

    async def test_high_risk_requires_approval(self):
        self.registry["fake_tool"] = ToolSpec(
            tool=self.tool,
            risk="high",
        )

        with self.assertRaises(Denied):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
            )

        self.assertEqual(self.tool.calls, 0)

    async def test_approved_high_risk_tool_executes(self):
        self.registry["fake_tool"] = ToolSpec(
            tool=self.tool,
            risk="high",
        )

        self.gateway.approval_callback = lambda *args: True

        result = await self.gateway.execute(
            "fake_tool",
            {},
            principal="user-1",
        )

        self.assertEqual(result, "success")
        self.assertEqual(self.tool.calls, 1)

    async def test_rejected_approval_prevents_execution(self):
        self.registry["fake_tool"] = ToolSpec(
            tool=self.tool,
            risk="high",
        )

        self.gateway.approval_callback = lambda *args: False

        with self.assertRaises(Denied):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
            )

        self.assertEqual(self.tool.calls, 0)

    async def test_async_approval_callback(self):
        self.registry["fake_tool"] = ToolSpec(
            tool=self.tool,
            risk="high",
        )

        async def approve(*args):
            return True

        self.gateway.approval_callback = approve

        await self.gateway.execute(
            "fake_tool",
            {},
            principal="user-1",
        )

        self.assertEqual(self.tool.calls, 1)

    # ---------------- Scope validation ----------------

    async def test_missing_scope_denies_execution(self):
        self.registry["fake_tool"] = ToolSpec(
            tool=self.tool,
            risk="low",
            scopes=frozenset({"mail.send"}),
        )

        with self.assertRaises(Denied):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
                granted_scopes={"mail.read"},
            )

        self.assertEqual(self.tool.calls, 0)

    async def test_granted_scope_allows_execution(self):
        self.registry["fake_tool"] = ToolSpec(
            tool=self.tool,
            risk="low",
            scopes=frozenset({"mail.send"}),
        )

        await self.gateway.execute(
            "fake_tool",
            {},
            principal="user-1",
            granted_scopes={"mail.send"},
        )

        self.assertEqual(self.tool.calls, 1)

    # ---------------- Rate limiting ----------------

    async def test_rate_limiter_receives_policy_limit(self):
        await self.gateway.execute(
            "fake_tool",
            {},
            principal="user-1",
        )

        self.assertEqual(
            self.rate_limiter.calls,
            [("user-1", "fake_tool", POLICIES["low"]["rate_per_min"])],
        )

    async def test_limit_none_skips_rate_limiter(self):
        with patch.dict(POLICIES["low"], {"rate_per_min": None}):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
            )

        self.assertEqual(self.rate_limiter.calls, [])

    async def test_rate_limit_denial_prevents_execution(self):
        self.rate_limiter.error = Denied("rate limit reached")

        with self.assertRaises(Denied):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
            )

        self.assertEqual(self.tool.calls, 0)
        self.assertEqual(self.audit.entries[-1]["outcome"], "blocked")

    # ---------------- Taint handling ----------------

    async def test_tainted_external_tool_requires_high_risk_approval(self):
        self.registry["fake_tool"] = ToolSpec(
            tool=self.tool,
            risk="low",
            external=True,
        )

        self.gateway.approval_callback = lambda *args: True

        await self.gateway.execute(
            "fake_tool",
            {},
            principal="user-1",
            tainted=True,
        )

        self.assertEqual(self.audit.entries[0]["risk"], "high")

    async def test_taint_producing_tool_requires_tracker(self):
        self.registry["fake_tool"] = ToolSpec(
            tool=self.tool,
            risk="low",
            taints=True,
        )

        with self.assertRaises(Denied):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
            )

        self.assertEqual(self.tool.calls, 0)

    async def test_taint_callback_is_called_after_execution(self):
        self.registry["fake_tool"] = ToolSpec(
            tool=self.tool,
            risk="low",
            taints=True,
        )

        calls = []

        def mark_tainted(context_id, tool_name):
            calls.append((context_id, tool_name))

        self.gateway.taint_callback = mark_tainted

        await self.gateway.execute(
            "fake_tool",
            {},
            principal="user-1",
            context_id="session-123",
        )

        self.assertEqual(
            calls,
            [("session-123", "fake_tool")],
        )

    # ---------------- Execution errors ----------------

    async def test_tool_error_is_audited_and_propagated(self):
        self.tool.error = RuntimeError("tool failed")

        with self.assertRaisesRegex(RuntimeError, "tool failed"):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
            )

        outcomes = [entry["outcome"] for entry in self.audit.entries]

        self.assertEqual(outcomes, ["allowed", "error"])

    # ---------------- Audit failures ----------------

    async def test_allowed_audit_failure_prevents_execution(self):
        self.audit.fail_on = "allowed"

        with self.assertRaises(OSError):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
            )

        self.assertEqual(self.tool.calls, 0)

    async def test_success_audit_failure_happens_after_execution(self):
        self.audit.fail_on = "ok"

        with self.assertRaises(OSError):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
            )

        # The tool has already executed.
        self.assertEqual(self.tool.calls, 1)

    # ---------------- Input validation ----------------

    async def test_empty_principal_is_rejected(self):
        with self.assertRaises(ValueError):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="",
            )

    async def test_string_granted_scopes_are_rejected(self):
        with self.assertRaises(TypeError):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
                granted_scopes="mail.send",
            )

    async def test_non_boolean_taint_is_rejected(self):
        with self.assertRaises(TypeError):
            await self.gateway.execute(
                "fake_tool",
                {},
                principal="user-1",
                tainted="yes",
            )


if __name__ == "__main__":
    unittest.main()
