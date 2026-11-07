"""Sliding-window rate limiter (in memory)."""
import threading
import time
from collections import deque

from .policy import Denied


class RateLimiter:
    def __init__(self, window=60.0, clock=time.monotonic):
        if isinstance(window, bool) or not isinstance(window, (int, float)) or window <= 0:
            raise ValueError(f"window must be a positive number of seconds, got {window!r}")
        self.window = window
        self._clock = clock
        self._hits = {}                       # plain dict: reading never creates entries
        self._lock = threading.Lock()
        self._next_sweep = clock() + window   # when to next clean out idle keys

    @staticmethod
    def _validate_limit(limit):
        """A bad limit is a bug in OUR config, so raise ValueError (not Denied)."""
        if limit is None:
            return
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError(f"limit must be None or a non-negative integer, got {limit!r}")

    def _prune(self, key):
        """Drop expired hits for one key.

        Returns the live deque, or None if the key has no hits left (in which
        case the key is deleted). Caller holds the lock.
        """
        hits = self._hits.get(key)
        if hits is None:
            return None
        now = self._clock()
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if not hits:
            del self._hits[key]
            return None
        return hits

    def _sweep(self):
        """At most once per window, remove EVERY key whose hits have all expired.

        Pruning on access only cleans keys that are used again. Keys of
        principals who never come back need this periodic sweep.
        Caller holds the lock.
        """
        now = self._clock()
        if now < self._next_sweep:
            return
        for key in list(self._hits):          # list(): we delete while looping
            self._prune(key)
        self._next_sweep = now + self.window

    def _denied(self, tool, limit):
        return Denied(f"rate limit reached for '{tool}' ({limit} per {self.window:g}s)")

    def check(self, principal, tool, limit):
        """Peek only: raise Denied if the limit is already reached. Does NOT count the call."""
        self._validate_limit(limit)
        if limit is None:
            return
        if limit == 0:
            raise self._denied(tool, limit)
        with self._lock:
            hits = self._prune((principal, tool))
            if hits is not None and len(hits) >= limit:
                raise self._denied(tool, limit)

    def acquire(self, principal, tool, limit):
        """Check the limit AND record the call in one atomic step."""
        self._validate_limit(limit)
        if limit == 0:
            raise self._denied(tool, limit)
        key = (principal, tool)
        with self._lock:
            self._sweep()
            hits = self._prune(key)
            if hits is not None and limit is not None and len(hits) >= limit:
                raise self._denied(tool, limit)
            if hits is None:
                hits = self._hits[key] = deque()
            hits.append(self._clock())


limiter = RateLimiter()