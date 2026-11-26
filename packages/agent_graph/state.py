from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class HumanInteractionRequest(TypedDict):
    """Safe, user-facing payload for a graph pause."""

    kind: Literal["clarification", "approval"]
    prompt: str
    options: list[str]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    human_request: NotRequired[HumanInteractionRequest]
    human_response: NotRequired[str | bool]
    