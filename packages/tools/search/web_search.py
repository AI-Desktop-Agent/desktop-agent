from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun

@tool
def web_search(query: str) -> str:
    """
        Search the web for current information about a topic.
        
        Use this tool when the user asks for information that needs
        web research, recent facts, or external sources.
    """
    if not query.strip():
        return "Search query cannot be empty."
    
    try:
        search = DuckDuckGoSearchRun()
        return search.run(query)
    except Exception as exc:
        return f"Web search failed: {exc}"