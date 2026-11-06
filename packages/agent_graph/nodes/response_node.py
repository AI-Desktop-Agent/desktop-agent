from packages.llm.llm_manager import llm_manager
from packages.agent_graph.state import AgentState
from packages.agent_graph.prompts.response_prompt import DESKTOP_AGENT_SYSTEM_PROMPT
from langchain_core.messages import SystemMessage
from packages.tools import TOOLS


async def response_node(state: AgentState) -> dict:
    llm_with_tools = llm_manager.get_chat_llm().bind_tools(TOOLS)

    messages = [
        SystemMessage(content=DESKTOP_AGENT_SYSTEM_PROMPT),
        *state["messages"]
    ]

    response = await llm_with_tools.ainvoke(messages)

    return {"messages": [response]}
