
# Importing web_search executes its secure_tool decorator
# and registers it in the security registry.
from packages.tools.search.web_search import web_search

from packages.security.registry import get_tools


TOOLS = get_tools()

__all__ = ["TOOLS"]
