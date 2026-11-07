import threading
import unittest

from packages.security.limits import RateLimiter
from packages.security.policy import Denied


class FakeClock:
    """A clock we control, so tests never have to sleep."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class TestLimits(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.limiter = RateLimiter(window=60, clock=self.clock)

    def use(self, times, principal="anon", tool="t", limit=3):
        for _ in range(times):
            self.limiter.acquire(principal, tool, limit)

    # --- basic behavior -------------------------------------------------
    def test_allows_calls_up_to_the_limit(self):
        self.use(3)

    def test_blocks_the_call_after_the_limit(self):
        self.use(3)
        with self.assertRaises(Denied):
            self.limiter.acquire("anon", "t", 3)

    def test_message_names_the_tool(self):
        self.use(3, tool="send_email")
        with self.assertRaises(Denied) as cm:
            self.limiter.acquire("anon", "send_email", 3)
        self.assertIn("send_email", str(cm.exception))

    def test_window_slides_and_frees_the_slot(self):
        self.use(3)
        self.clock.advance(61)
        self.limiter.acquire("anon", "t", 3)

    def test_old_calls_expire_one_by_one(self):
        self.use(1)                 # t = 0
        self.clock.advance(30)
        self.use(1)                 # t = 30
        self.clock.advance(20)
        self.use(1)                 # t = 50: three calls in the window
        self.clock.advance(11)      # t = 61: the call at t = 0 has expired
        self.limiter.acquire("anon", "t", 3)
        with self.assertRaises(Denied):
            self.limiter.acquire("anon", "t", 3)

    def test_each_tool_has_its_own_count(self):
        self.use(3, tool="a")
        self.limiter.acquire("anon", "b", 3)

    def test_each_principal_has_its_own_count(self):
        self.use(3, principal="alice")
        self.limiter.acquire("bob", "t", 3)

    def test_none_means_no_limit(self):
        for _ in range(1000):
            self.limiter.acquire("anon", "t", None)
        self.limiter.check("anon", "t", None)

    # --- zero limit -----------------------------------------------------
    def test_zero_limit_always_denies_and_leaves_no_trace(self):
        with self.assertRaises(Denied):
            self.limiter.check("anon", "t", 0)
        with self.assertRaises(Denied):
            self.limiter.acquire("anon", "t", 0)
        self.assertNotIn(("anon", "t"), self.limiter._hits)

    # --- validation -----------------------------------------------------
    def test_bad_window_is_rejected(self):
        for bad in (0, -5, True, "60", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                RateLimiter(window=bad)

    def test_bad_limit_is_rejected(self):
        for bad in (True, False, "5", 5.0, -1, [3]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                self.limiter.check("anon", "t", bad)
            with self.assertRaises(ValueError, msg=repr(bad)):
                self.limiter.acquire("anon", "t", bad)

    # --- check vs acquire -----------------------------------------------
    def test_check_alone_does_not_use_up_the_limit(self):
        for _ in range(10):
            self.limiter.check("anon", "t", 3)

    def test_check_agrees_with_acquire(self):
        self.use(3)
        with self.assertRaises(Denied):
            self.limiter.check("anon", "t", 3)

    def test_a_denied_acquire_is_not_recorded(self):
        self.use(3)                      # t = 0
        self.clock.advance(30)
        with self.assertRaises(Denied):  # refused at t = 30, must leave no mark
            self.limiter.acquire("anon", "t", 3)
        self.clock.advance(31)           # t = 61: the three real calls expired
        self.use(3)                      # would fail if the refused call had counted

    def test_a_burst_in_one_go_cannot_exceed_the_limit(self):
        allowed = 0
        for _ in range(10):
            try:
                self.limiter.acquire("anon", "t", 5)
                allowed += 1
            except Denied:
                pass
        self.assertEqual(allowed, 5)

    def test_threads_cannot_exceed_the_limit(self):
        limiter = RateLimiter(window=60, clock=self.clock)
        barrier = threading.Barrier(20)
        results = []

        def worker():
            barrier.wait()
            try:
                limiter.acquire("anon", "t", 5)
                results.append(True)
            except Denied:
                results.append(False)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count(True), 5)

    # --- memory: idle keys must not pile up ------------------------------
    def test_check_never_creates_entries(self):
        for i in range(50):
            self.limiter.check(f"user{i}", "t", 3)
        self.assertEqual(len(self.limiter._hits), 0)

    def test_expired_key_is_removed_when_touched_again(self):
        self.use(1)
        self.clock.advance(61)
        self.limiter.check("anon", "t", 3)
        self.assertNotIn(("anon", "t"), self.limiter._hits)

    def test_keys_of_principals_who_never_return_are_swept(self):
        for i in range(100):
            self.limiter.acquire(f"user{i}", "t", 3)
        self.assertEqual(len(self.limiter._hits), 100)
        self.clock.advance(61)
        self.limiter.acquire("newcomer", "t", 3)       # triggers the sweep
        self.assertEqual(len(self.limiter._hits), 1)

    def test_sweep_keeps_keys_that_still_have_live_hits(self):
        self.limiter.acquire("alice", "t", 3)           # t = 0
        self.clock.advance(50)
        self.limiter.acquire("alice", "t", 3)           # t = 50
        self.clock.advance(11)                          # t = 61: first hit expired
        self.limiter.acquire("bob", "t", 3)             # triggers the sweep
        self.assertEqual(len(self.limiter._hits[("alice", "t")]), 1)
        self.assertEqual(len(self.limiter._hits), 2)

    def test_counting_still_correct_after_a_key_was_cleaned_up(self):
        self.use(3)
        self.clock.advance(61)
        self.use(3)                                     # key was deleted, recreated
        with self.assertRaises(Denied):
            self.limiter.acquire("anon", "t", 3)

    # --- the exact boundary (we chose: a call exactly `window` old still counts)
    def test_call_exactly_one_window_old_still_counts(self):
        self.limiter.acquire("anon", "t", 1)
        self.clock.advance(60)
        with self.assertRaises(Denied):
            self.limiter.acquire("anon", "t", 1)
        self.clock.advance(0.001)
        self.limiter.acquire("anon", "t", 1)


if __name__ == "__main__":
    unittest.main()