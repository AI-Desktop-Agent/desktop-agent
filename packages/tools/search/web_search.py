
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from packages.security.registry import secure_tool

@secure_tool(risk="medium", external=True, taints=True)
@tool
async def web_search(query: str) -> str:
    """
    Search the web for current information about a topic.
    Use this tool when the user asks for information that needs
    web research, recent facts, or external sources.
    """
    if not query.strip():
        return "Search query cannot be empty."

    try:
        search = DuckDuckGoSearchRun()
        return await search.arun(query)

    except Exception as exc:
        return f"Web search failed: {exc}"
