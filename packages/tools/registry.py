from packages.security.registry import get_tools
from .search.web_search import web_search
from .command_line.command_executor_tool import command_executor_tool


# Explicitly specify tools available to the LLM
AVAILABLE_TOOLS_NAMES = {
    "web_search",
    "command_executor_tool"
}


# Get only the tools allowed for the LLM
TOOLS = [
    tool
    for tool in get_tools()
    if tool.name in AVAILABLE_TOOLS_NAMES
]


__all__ = ["TOOLS"]
