from langgraph.graph import StateGraph, START
from packages.agent_graph.nodes.response_node import response_node
from packages.agent_graph.state import AgentState
from packages.tools import TOOLS
from langgraph.prebuilt import ToolNode, tools_condition


builder = StateGraph(AgentState)


builder.add_node("response_node", response_node)
builder.add_node("tools", ToolNode(TOOLS))


builder.add_edge(START, 'response_node')
builder.add_conditional_edges(
    'response_node',
    tools_condition
)
builder.add_edge('tools', 'response_node')

agent_graph = builder.compile()
