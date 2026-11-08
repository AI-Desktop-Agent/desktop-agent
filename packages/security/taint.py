
import threading


class TaintTracker:
    """Tracks whether a conversation has received untrusted content."""

    def __init__(self):
        self._tainted_contexts = set()
        self._lock = threading.Lock()

    def mark_tainted(self, context_id, tool_name):
        with self._lock:
            self._tainted_contexts.add(context_id)

    def is_tainted(self, context_id):
        with self._lock:
            return context_id in self._tainted_contexts

    def clear(self, context_id):
        with self._lock:
            self._tainted_contexts.discard(context_id)


taint_tracker = TaintTracker()
