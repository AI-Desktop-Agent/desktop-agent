from packages.llm.llm_manager import llm_manager
from packages.agent_graph.state import AgentState
from packages.agent_graph.prompts.response_prompt import DESKTOP_AGENT_SYSTEM_PROMPT
from langchain_core.messages import SystemMessage
from packages.tools import TOOLS

def response_node(state: AgentState) -> dict:
    # Get the chat LLM from the LLM manager
    llm_with_tools = llm_manager.get_chat_llm().bind_tools(TOOLS)
    
    # messages
    messages = [
        SystemMessage(content=DESKTOP_AGENT_SYSTEM_PROMPT),
        *state['messages']
    ]
    # Generate a response based on the messages in the state
    response = llm_with_tools.invoke(messages)
    
    return {'messages': [response]}