import subprocess
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage

from packages.security.registry import secure_tool
from packages.security.gateway import gateway
from packages.security.policy import Denied

from packages.llm.llm_manager import llm_manager

from packages.tools.command_line.schemas import CommandPlan
from packages.tools.command_line.command_validator import (
    validate_command_plan,
    CommandValidationError,
)

# Importing this module registers the internal executor
# through its @secure_tool decorator.
from packages.tools.command_line.command_executor_tool import (
    command_executor_tool,
)
from .prompts import COMMAND_INTERPRETER_SYSTEM_PROMPT
from .command_registry import COMMAND_RISK_MAPPING



def get_available_command_descriptions() -> str:
    """
    Retrieve Windows command descriptions using the built-in HELP command.

    Only commands present in our trusted command registry are returned.
    """

    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "help"],
            shell=False,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError("Windows HELP command failed.")

        help_output = result.stdout

        registered_commands = {
            command.upper().strip()
            for risk, commands in COMMAND_RISK_MAPPING.items()
            if risk != "blocked"
            for command in commands
        }

        descriptions = []

        for line in help_output.splitlines():

            line = line.strip()

            if not line:
                continue

            parts = line.split(maxsplit=1)

            if not parts:
                continue

            command_name = parts[0].upper()

            if command_name in registered_commands:
                description = parts[1] if len(parts) > 1 else "No description available."

                descriptions.append(
                    f"{command_name}: {description}"
                )

        if not descriptions:
            raise RuntimeError(
                "No registered command descriptions were found."
            )

        return "\n".join(descriptions)

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Timed out while retrieving Windows command descriptions."
        ) from exc

    except OSError as exc:
        raise RuntimeError(
            f"Unable to retrieve Windows command descriptions: {exc}"
        ) from exc


# ---------------------------------------------------------
# 1. Generate structured command plan
# ---------------------------------------------------------

async def generate_command_plan(user_request: str) -> CommandPlan:
    """
    Ask the structured LLM to interpret the user's request.
    """

    structured_provider = llm_manager.get_structured_llm()

    # OpenRouterLLM is a wrapper around ChatOpenAI.
    # Initialize its underlying LangChain client if necessary.
    if structured_provider.client is None:
        structured_provider.initialize_client()

    structured_llm = structured_provider.client.with_structured_output(
        CommandPlan,
        method="function_calling",
    )

    command_descriptions = get_available_command_descriptions()

    messages = [
        SystemMessage(content=COMMAND_INTERPRETER_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"USER REQUEST:\n{user_request}\n\n"
                f"AVAILABLE COMMANDS:\n{command_descriptions}"
            )
        ),
    ]

    return await structured_llm.ainvoke(messages)


# ---------------------------------------------------------
# 2. Validate generated plan
# ---------------------------------------------------------

def verify_command_plan(plan: CommandPlan) -> CommandPlan:
    """
    Validate the generated plan before execution.
    """

    if plan.status != "ready":
        return plan

    return validate_command_plan(plan)


# ---------------------------------------------------------
# 3. Execute through Security Gateway
# ---------------------------------------------------------

async def execute_validated_command(plan: CommandPlan) -> dict:
    """
    Send a validated command to the internal executor
    through the Security Gateway.
    """

    return await gateway.execute(
        tool_name="command_executor_tool",
        args={
            "command_name": plan.command_name,
            "arguments": plan.arguments,
        },
        principal="desktop-agent",
    )


# ---------------------------------------------------------
# 4. Main public tool
# ---------------------------------------------------------

@secure_tool(risk="medium")
@tool
async def command_line_tool(request: str) -> dict:
    """
    Interpret and execute a Windows command requested by the user.

    Use this tool for supported Windows command-line operations.
    It interprets the request, validates the command, and sends
    it through the Security Gateway before execution.
    """

    if not request or not request.strip():
        return {
            "success": False,
            "status": "invalid_request",
            "message": "Command request cannot be empty.",
        }

    try:
        # Step 1: Generate structured output.
        plan = await generate_command_plan(request)

        # Step 2: Handle clarification and unsupported requests.
        if plan.status == "clarification_required":
            return {
                "success": False,
                "status": "clarification_required",
                "message": plan.explanation,
            }

        if plan.status == "unsupported":
            return {
                "success": False,
                "status": "unsupported",
                "message": plan.explanation,
            }

        # Step 3: Validate the generated command.
        validated_plan = verify_command_plan(plan)

        # Step 4: Execute through the Security Gateway.
        result = await execute_validated_command(validated_plan)

        return {
            "success": True,
            "status": "executed",
            "command": validated_plan.command_name,
            "explanation": validated_plan.explanation,
            "result": result,
        }

    except CommandValidationError as exc:
        return {
            "success": False,
            "status": "validation_failed",
            "message": str(exc),
        }

    except Denied as exc:
        return {
            "success": False,
            "status": "execution_denied",
            "message": str(exc),
        }

    except Exception as exc:
        return {
            "success": False,
            "status": "error",
            "message": f"{type(exc).__name__}: {exc}",
        }
