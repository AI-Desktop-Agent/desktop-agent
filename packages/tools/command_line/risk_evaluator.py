
from .command_registry import COMMAND_RISK_MAPPING


def _build_lookup(mapping: dict) -> dict:
    lookup = {}

    for risk, commands in mapping.items():
        for command in commands:
            command = command.upper().strip()

            if command in lookup:
                raise ValueError(
                    f"Duplicate command '{command}' found "
                    f"in '{lookup[command]}' and '{risk}'"
                )

            lookup[command] = risk

    return lookup


COMMAND_TIER = _build_lookup(COMMAND_RISK_MAPPING)


def get_command_risk(args: dict) -> str:
    """
    Determine risk based on the selected command.
    Unknown or invalid commands are blocked.
    """

    if not isinstance(args, dict):
        return "blocked"

    command = args.get("command_name")

    if not isinstance(command, str) or not command.strip():
        return "blocked"

    command = command.upper().strip()

    return COMMAND_TIER.get(command, "blocked")