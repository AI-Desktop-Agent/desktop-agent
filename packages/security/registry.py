"""Tool registry: a tool that is not registered here can never run."""
from dataclasses import dataclass
from typing import Any, Callable, Union

from .policy import POLICIES

RiskSpec = Union[str, Callable[[dict], str]]

@dataclass(frozen=True)
class ToolSpec:
    tool: Any
    risk: RiskSpec
    scopes: frozenset = frozenset()
    external: bool = False
    taints: bool = False
    
REGISTRY: dict[str, ToolSpec] = {}

def secure_tool(risk: RiskSpec = "high", *, scopes=(), external=False, taints=False):
    """
        Register a tool with the gateway. Put it ABOVE @tool.
        Forgetting to choose a risk give "high" (fail closed).
    """
    if isinstance(risk, str) and risk not in POLICIES:
        raise ValueError(f"unknown risk tier '{risk}', choose from {list(POLICIES)}")
    
    if isinstance(scopes, str):
        raise TypeError("scopes must be a list or tuple like ['mail.send'], not a string")
    
    def deco(tool_obj):
        name = getattr(tool_obj, "name", None)
        if not name or not hasattr(tool_obj, "invoke"):
            raise TypeError("@secure_tool must be placed above @tool")
        if name in REGISTRY:
            raise ValueError(f"tool '{name}' is already registered")
        REGISTRY[name] = ToolSpec(
            tool=tool_obj,
            risk=risk,
            scopes=frozenset(scopes),
            external=external,
            taints=taints
        )
        return tool_obj
    
    return deco

def get_tools():
    """The tool objects to bind to the model"""
    return [spec.tool for spec in REGISTRY.values()]
    