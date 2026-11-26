from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ApplicationSpec:
    name: str
    executable_paths: tuple[str, ...]
    risk: str
    arguments_allowed: bool = False
    aliases: tuple[str, ...] = ()
    category: str | None = None
    category_aliases: tuple[str, ...] = ()


APPLICATIONS: dict[str, ApplicationSpec] = {
    "notepad": ApplicationSpec(
        name="notepad",
        executable_paths=(
            r"C:\Windows\System32\notepad.exe",
        ),
        risk="low",
        aliases=("text editor",),
        category="text editor",
        category_aliases=("text editor", "plain text editor"),
    ),
    "calculator": ApplicationSpec(
        name="calculator",
        executable_paths=(
            r"C:\Windows\System32\calc.exe",
            r"C:\Windows\Sysnative\calc.exe",
        ),
        risk="low",
        aliases=("calc",),
        category="calculator",
        category_aliases=("calculator", "calculation app"),
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
        category="browser",
        category_aliases=("browser", "web browser"),
    ),
    "edge": ApplicationSpec(
        name="edge",
        executable_paths=(
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
        ),
        risk="medium",
        arguments_allowed=True,
        aliases=("microsoft edge", "ms edge"),
        category="browser",
        category_aliases=("browser", "web browser"),
    ),
    "vscode": ApplicationSpec(
        name="vscode",
        executable_paths=(
            r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe",
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ),
        risk="medium",
        aliases=("visual studio code", "code"),
        category="code editor",
        category_aliases=("code editor", "programming editor", "ide"),
    ),
    "explorer": ApplicationSpec(
        name="explorer",
        executable_paths=(
            r"C:\Windows\explorer.exe",
        ),
        risk="medium",
        aliases=("file explorer", "windows explorer"),
        category="file manager",
        category_aliases=("file manager", "file explorer"),
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


def normalize_application_category(category: str) -> str:
    if not isinstance(category, str):
        return ""

    return " ".join(
        category.strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .split()
    )


def get_category_application_names(category: str) -> tuple[str, ...]:
    normalized_category = normalize_application_category(category)

    if not normalized_category:
        return ()

    matches = []

    for candidate in APPLICATIONS.values():
        category_names = {normalize_application_category(candidate.category or "")}
        category_names.update(
            normalize_application_category(category_alias)
            for category_alias in candidate.category_aliases
        )

        if normalized_category in category_names:
            matches.append(candidate.name)

    return tuple(sorted(set(matches)))


def get_category_application_specs(category: str) -> tuple[ApplicationSpec, ...]:
    names = get_category_application_names(category)
    return tuple(
        APPLICATIONS[name]
        for name in names
        if name in APPLICATIONS
    )


def resolve_application_or_category(
    application: str,
) -> tuple[ApplicationSpec | None, tuple[str, ...]]:
    spec = get_application_spec(application)
    if spec is not None:
        return spec, ()

    return None, get_category_application_names(application)


def get_application_risk(args: dict) -> str:
    if not isinstance(args, dict):
        return "blocked"

    application = args.get("application")
    spec = get_application_spec(application)

    if spec is None:
        category_names = get_category_application_names(application)
        if category_names:
            arguments = args.get("arguments", [])
            if arguments:
                return "high"
            return "medium"
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