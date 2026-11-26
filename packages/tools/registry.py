from packages.security.registry import get_tools
from .search.web_search import web_search
from .applications.application_tool import open_application
from .clarification_tool import ask_clarification


# Explicitly specify tools available to the LLM
AVAILABLE_TOOLS_NAMES = {
    "web_search",
    "open_application",
    "ask_clarification",
}


# Get only the tools allowed for the LLM
TOOLS = [
    tool
    for tool in get_tools()
    if tool.name in AVAILABLE_TOOLS_NAMES
]


__all__ = ["TOOLS"]
