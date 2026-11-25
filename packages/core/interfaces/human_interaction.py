from collections.abc import Mapping, Sequence
from typing import Protocol


class HumanInteraction(Protocol):
    """Human input operations used by graph clarification and tool approval."""

    async def ask_clarification(
        self,
        question: str,
        options: Sequence[str] | None = None,
    ) -> str:
        """Ask the user for missing information and return their answer."""
        ...

    async def request_approval(
        self,
        tool_name: str,
        risk: str,
        args: Mapping[str, object],
        principal: str,
    ) -> bool:
        """Return True only when the user explicitly approves the action."""
        ...
