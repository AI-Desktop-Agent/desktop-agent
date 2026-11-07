import unittest

from packages.security.policy import POLICIES, RISK_ORDER, resolve_risk, worst


class TestPolicy(unittest.TestCase):
    def test_every_tier_has_a_policy(self):
        for tier in RISK_ORDER:
            self.assertIn(tier, POLICIES)

    def test_worst_picks_the_more_dangerous(self):
        self.assertEqual(worst("low", "high"), "high")
        self.assertEqual(worst("destructive", "medium", "low"), "destructive")

    def test_plain_tier_name(self):
        self.assertEqual(resolve_risk("low", {}), "low")

    def test_risk_function_sees_the_arguments(self):
        def risk(args):
            return "destructive" if args["action"] == "delete" else "low"

        self.assertEqual(resolve_risk(risk, {"action": "delete"}), "destructive")
        self.assertEqual(resolve_risk(risk, {"action": "read"}), "low")

    def test_unknown_tier_fails_closed(self):
        self.assertEqual(resolve_risk("banana", {}), "high")

    def test_crashing_risk_function_fails_closed(self):
        self.assertEqual(resolve_risk(lambda a: a["missing"], {}), "high")

    def test_taint_raises_external_tools(self):
        self.assertEqual(resolve_risk("low", {}, external=True, tainted=True), "high")

    def test_taint_ignores_non_external_tools(self):
        self.assertEqual(resolve_risk("low", {}, external=False, tainted=True), "low")

    def test_taint_never_lowers_risk(self):
        self.assertEqual(
            resolve_risk("destructive", {}, external=True, tainted=True), "destructive"
        )


if __name__ == "__main__":
    unittest.main()