from langchain_core.tools import tool
from langgraph.types import interrupt

from packages.security.registry import secure_tool
from packages.tools.applications.application_launcher import (
    ApplicationLaunchError,
    ApplicationLauncher,
)
from packages.tools.applications.application_registry import get_application_risk
from packages.tools.applications.application_registry import (
    get_application_spec,
    resolve_application_or_category,
)


@secure_tool(risk=get_application_risk)
@tool
def open_application(
    application: str,
    arguments: list[str] | None = None,
) -> dict:
    """
    Launch a registered Windows application.

    The application name must match the application registry. Arguments are
    optional only for applications that explicitly allow them. Execution is
    authorized by the Security Gateway and is never done through a shell.
    """
    if not isinstance(application, str) or not application.strip():
        return {
            "success": False,
            "status": "invalid_application",
            "message": "Application name cannot be empty.",
        }

    if arguments is not None and not isinstance(arguments, list):
        return {
            "success": False,
            "status": "invalid_arguments",
            "message": "Arguments must be a list of strings.",
        }

    exact_spec, category_names = resolve_application_or_category(application)

    if exact_spec is None:
        available_names = []
        for category_name in category_names:
            category_spec = get_application_spec(category_name)
            if (
                category_spec is not None
                and ApplicationLauncher.is_available(category_spec)
            ):
                available_names.append(category_name)

        if not available_names:
            return {
                "success": False,
                "status": "unsupported_application",
                "application": application.strip(),
                "message": "No registered application is available for this category.",
            }

        if len(available_names) == 1:
            application = available_names[0]
        else:
            choice = interrupt(
                {
                    "kind": "clarification",
                    "prompt": f"Which {application.strip()} application should I open?",
                    "options": available_names,
                }
            )

            if not isinstance(choice, str):
                return {
                    "success": False,
                    "status": "invalid_response",
                    "message": "Application choice must be text.",
                }

            choice = choice.strip().lower()
            selected_spec = get_application_spec(choice)
            if (
                selected_spec is None
                or choice not in available_names
                or not ApplicationLauncher.is_available(selected_spec)
            ):
                return {
                    "success": False,
                    "status": "invalid_response",
                    "message": "Selected application is not available.",
                }

            application = selected_spec.name

    try:
        return ApplicationLauncher.launch(
            application=application.strip(),
            arguments=arguments,
        )
    except ApplicationLaunchError as exc:
        return {
            "success": False,
            "status": "launch_failed",
            "application": application.strip(),
            "message": str(exc),
        }