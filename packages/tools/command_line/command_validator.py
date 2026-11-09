
import re

from packages.tools.command_line.command_registry import COMMAND_RISK_MAPPING
from packages.tools.command_line.schemas import CommandPlan


class CommandValidationError(ValueError):
    """Raised when an LLM-generated command fails validation."""


# Build a lookup of all registered command names and their risk tiers.
COMMAND_TIER = {
    command.upper().strip(): risk
    for risk, commands in COMMAND_RISK_MAPPING.items()
    for command in commands
}


# Validation limits
MAX_ARGUMENTS = 32
MAX_ARGUMENT_LENGTH = 2048
MAX_TOTAL_ARGUMENT_LENGTH = 8192


def validate_command_plan(plan: CommandPlan) -> CommandPlan:
    """
    Validate and normalize an LLM-generated command plan.

    Returns:
        A validated CommandPlan.

    Raises:
        CommandValidationError: If validation fails.
    """

    if not isinstance(plan, CommandPlan):
        raise CommandValidationError(
            "Expected a CommandPlan object."
        )

    # 1. Check LLM interpretation status.
    if plan.status != "ready":
        raise CommandValidationError(
            f"Command cannot be executed. Status: {plan.status}"
        )

    # 2. Validate and normalize command name.
    if not isinstance(plan.command_name, str):
        raise CommandValidationError("Invalid command name.")

    command_name = plan.command_name.strip().upper()

    if not command_name:
        raise CommandValidationError("Command name cannot be empty.")

    if not re.fullmatch(r"[A-Z][A-Z0-9]*", command_name):
        raise CommandValidationError(
            "Command name contains invalid characters."
        )

    # 3. Check command allowlist and risk classification.
    risk = COMMAND_TIER.get(command_name)

    if risk is None:
        raise CommandValidationError(
            f"Unsupported command: {command_name}"
        )

    if risk == "blocked":
        raise CommandValidationError(
            f"Command '{command_name}' is blocked."
        )

    # 4. Validate argument collection.
    if not isinstance(plan.arguments, list):
        raise CommandValidationError(
            "Arguments must be a list."
        )

    if len(plan.arguments) > MAX_ARGUMENTS:
        raise CommandValidationError(
            "Too many command arguments."
        )

    total_length = 0

    for argument in plan.arguments:

        if not isinstance(argument, str):
            raise CommandValidationError(
                "Every command argument must be a string."
            )

        if not argument:
            raise CommandValidationError(
                "Empty command arguments are not allowed."
            )

        if len(argument) > MAX_ARGUMENT_LENGTH:
            raise CommandValidationError(
                "Command argument exceeds the maximum length."
            )

        # Reject null bytes, newlines, tabs and other control characters.
        if any(ord(char) < 32 or ord(char) == 127 for char in argument):
            raise CommandValidationError(
                "Command arguments cannot contain control characters."
            )

        # Reject UNC paths and Windows device paths.
        if argument.startswith("\\\\"):
            raise CommandValidationError(
                "UNC and Windows device paths are not allowed."
            )

        total_length += len(argument)

    if total_length > MAX_TOTAL_ARGUMENT_LENGTH:
        raise CommandValidationError(
            "Total command argument length exceeded."
        )

    # 5. Return a normalized plan.
    return plan.model_copy(
        update={"command_name": command_name}
    )
