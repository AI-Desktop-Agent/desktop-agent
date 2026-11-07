"""Risk tiers and the rules attached to each tier."""

class Denied(Exception):
    """Raise this from any check to stop a tool call."""

RISK_ORDER = ["low", "medium", "high", "destructive", "blocked"]

POLICIES = {
    "low": {"approval": False, "rate_per_min": 60},
    "medium": {"approval": False, "rate_per_min": 20},
    "high": {"approval": True, "rate_per_min": 5},
    "destructive": {"approval": True, "rate_per_min": 2},
    "blocked": {"approval": False, "rate_per_min": 0, "deny": True},
}

def worst(*risks):
    """Return the most dangerous risk. Unknown values count as "high"."""
    cleaned = [
        r if isinstance(r, str) and r in POLICIES else "high"
        for r in risks
    ]
    if not cleaned:
        return "high"
    return max(cleaned, key=RISK_ORDER.index)

# After untrusted content (a web page, an email) enters the session, tools that
# send data out are treated as at least this risky.
TAINT_FLOOR = "high"

def resolve_risk(risk, args, *, external=False, tainted=False):
    """Resolve the risk level for one tool call."""
    
    try:
        level = risk(args) if callable(risk) else risk
    except Exception:
        level = "high"
    
    if not isinstance(level, str) or level not in POLICIES:
        level = "high"
        
    if tainted and external:
        level = worst(level, TAINT_FLOOR)
        
    return level