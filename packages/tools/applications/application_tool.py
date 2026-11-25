from langchain_core.tools import tool

from packages.security.registry import secure_tool
from packages.tools.applications.application_launcher import (
    ApplicationLaunchError,
    ApplicationLauncher,
)
from packages.tools.applications.application_registry import get_application_risk


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