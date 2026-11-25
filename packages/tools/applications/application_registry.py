from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ApplicationSpec:
    name: str
    executable_paths: tuple[str, ...]
    risk: str
    arguments_allowed: bool = False
    aliases: tuple[str, ...] = ()


APPLICATIONS: dict[str, ApplicationSpec] = {
    "notepad": ApplicationSpec(
        name="notepad",
        executable_paths=(
            r"C:\Windows\System32\notepad.exe",
        ),
        risk="low",
    ),
    "calculator": ApplicationSpec(
        name="calculator",
        executable_paths=(
            r"C:\Windows\System32\calc.exe",
            r"C:\Windows\Sysnative\calc.exe",
        ),
        risk="low",
        aliases=("calc",),
    ),
    "chrome": ApplicationSpec(
        name="chrome",
        executable_paths=(
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
        ),
        risk="medium",
        arguments_allowed=True,
        aliases=("google chrome", "google-chrome"),
    ),
    "vscode": ApplicationSpec(
        name="vscode",
        executable_paths=(
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ),
        risk="medium",
        aliases=("visual studio code", "code"),
    ),
    "explorer": ApplicationSpec(
        name="explorer",
        executable_paths=(
            r"C:\Windows\explorer.exe",
        ),
        risk="medium",
        aliases=("file explorer", "windows explorer"),
    ),
}


def _normalize_application_name(application: str) -> str:
    if not isinstance(application, str):
        return ""

    return " ".join(application.strip().lower().replace("_", " ").replace("-", " ").split())


def get_application_spec(application: str) -> ApplicationSpec | None:
    normalized_name = _normalize_application_name(application)

    if not normalized_name:
        return None

    spec = APPLICATIONS.get(normalized_name)
    if spec is not None:
        return spec

    for candidate in APPLICATIONS.values():
        normalized_aliases = {
            _normalize_application_name(alias)
            for alias in candidate.aliases
        }
        if normalized_name in normalized_aliases:
            return candidate

    return None


def get_application_risk(args: dict) -> str:
    if not isinstance(args, dict):
        return "blocked"

    spec = get_application_spec(args.get("application"))

    if spec is None:
        return "blocked"

    if spec.risk not in {"low", "medium", "high", "destructive", "blocked"}:
        return "blocked"

    arguments = args.get("arguments", [])
    if arguments is None:
        arguments = []

    if not isinstance(arguments, (list, tuple)):
        return "blocked"

    if arguments:
        return "high"

    return spec.risk


def get_registered_application_names() -> tuple[str, ...]:
    return tuple(APPLICATIONS)


def iter_application_specs() -> Iterable[ApplicationSpec]:
    return APPLICATIONS.values()