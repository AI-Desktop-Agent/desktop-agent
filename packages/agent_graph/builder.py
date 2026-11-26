from langgraph.graph import StateGraph, START
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import InMemorySaver

from packages.agent_graph.nodes.response_node import response_node
from packages.agent_graph.nodes.tool_node import secure_tool_node
from packages.agent_graph.state import AgentState


builder = StateGraph(AgentState)

builder.add_node("response_node", response_node)
builder.add_node("tools", secure_tool_node)

builder.add_edge(START, "response_node")
builder.add_conditional_edges("response_node", tools_condition)
builder.add_edge("tools", "response_node")

checkpointer = InMemorySaver()
agent_graph = builder.compile(checkpointer=checkpointer)
