from langgraph.graph import StateGraph, START, END
from packages.agent_graph.nodes.response_node import response_node
from packages.agent_graph.state import AgentState


builder = StateGraph(AgentState)


builder.add_node(response_node)


builder.add_edge(START, response_node)
builder.add_edge(response_node, END)

agent_graph = builder.compile()
