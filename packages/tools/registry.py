from packages.security.registry import get_tools


# Explicitly specify tools available to the LLM
AVAILABLE_TOOLS_NAMES = {
    "web_search",
}


# Get only the tools allowed for the LLM
TOOLS = [
    tool
    for tool in get_tools()
    if tool.name in AVAILABLE_TOOLS_NAMES
]


__all__ = ["TOOLS"]
