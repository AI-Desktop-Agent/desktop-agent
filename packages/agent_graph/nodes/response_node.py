from packages.llm.llm_manager import llm_manager
from packages.agent_graph.state import AgentState

def response_node(state: AgentState) -> AgentState:
    # Get the chat LLM from the LLM manager
    chat_llm = llm_manager.get_chat_llm()
    
    # Generate a response based on the messages in the state
    response = chat_llm.invoke(state['messages'])
    
    # Update the state with the new response
    state['messages'].append(response)
    
    return state