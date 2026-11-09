
from langchain_core.tools import tool

from packages.security.registry import secure_tool
from packages.tools.command_line.executor import CommandExecutor
from packages.tools.command_line.risk_evaluator import get_command_risk


@secure_tool(risk=get_command_risk)
@tool
def command_executor_tool(command_name: str, arguments: list[str]) -> dict:
    """
    Execute a validated command through the command executor.

    Security authorization is handled by the Security Gateway.
    This tool must only be invoked through the Gateway.
    """

    command = [command_name, *arguments]

    return CommandExecutor.execute(command)
