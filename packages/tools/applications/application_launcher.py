import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from packages.tools.applications.application_registry import (
    ApplicationSpec,
    get_application_spec,
)


class ApplicationLaunchError(Exception):
    pass


class ApplicationLauncher:
    MAX_ARGUMENTS = 32
    MAX_ARGUMENT_LENGTH = 2048
    _CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")

    @classmethod
    def _expand_executable_path(cls, raw_path: str) -> Path:
        expanded_path = os.path.expandvars(raw_path)
        return Path(expanded_path).resolve(strict=False)

    @classmethod
    def _find_executable(cls, spec: ApplicationSpec) -> Path:
        for raw_path in spec.executable_paths:
            executable = cls._expand_executable_path(raw_path)

            if executable.is_file():
                return executable

        raise ApplicationLaunchError(
            f"No executable was found for application '{spec.name}'."
        )

    @classmethod
    def _validate_arguments(
        cls,
        spec: ApplicationSpec,
        arguments: list[str] | tuple[str, ...],
    ) -> list[str]:
        if not isinstance(arguments, (list, tuple)):
            raise ApplicationLaunchError("Arguments must be a list of strings.")

        if not arguments:
            return []

        if not spec.arguments_allowed:
            raise ApplicationLaunchError(
                f"Arguments are not allowed for application '{spec.name}'."
            )

        if spec.name != "chrome" or len(arguments) != 1:
            raise ApplicationLaunchError(
                f"Only one URL argument is supported for '{spec.name}'."
            )

        if len(arguments) > cls.MAX_ARGUMENTS:
            raise ApplicationLaunchError(
                f"No more than {cls.MAX_ARGUMENTS} arguments are allowed."
            )

        validated_arguments: list[str] = []

        for argument in arguments:
            if not isinstance(argument, str):
                raise ApplicationLaunchError(
                    "Every application argument must be a string."
                )

            if not argument:
                raise ApplicationLaunchError(
                    "Empty application arguments are not allowed."
                )

            if len(argument) > cls.MAX_ARGUMENT_LENGTH:
                raise ApplicationLaunchError(
                    "An application argument exceeds the maximum length."
                )

            if cls._CONTROL_CHARACTERS.search(argument):
                raise ApplicationLaunchError(
                    "Application arguments cannot contain control characters."
                )

            parsed_url = urlsplit(argument)
            if (
                parsed_url.scheme.lower() not in {"http", "https"}
                or not parsed_url.hostname
                or parsed_url.username is not None
                or parsed_url.password is not None
                or argument.startswith("-")
            ):
                raise ApplicationLaunchError(
                    "Chrome accepts only a valid HTTP or HTTPS URL."
                )

            validated_arguments.append(argument)

        return validated_arguments

    @classmethod
    def launch(
        cls,
        application: str,
        arguments: list[str] | tuple[str, ...] | None = None,
    ) -> dict:
        spec = get_application_spec(application)

        if spec is None:
            raise ApplicationLaunchError(
                f"Unknown or blocked application: {application}"
            )

        if spec.risk == "blocked":
            raise ApplicationLaunchError(
                f"Application '{spec.name}' is blocked."
            )

        validated_arguments = cls._validate_arguments(
            spec,
            arguments or [],
        )

        if os.name != "nt":
            raise ApplicationLaunchError(
                "Application launching is only supported on Windows."
            )

        executable = cls._find_executable(spec)
        command = [str(executable), *validated_arguments]

        try:
            process = subprocess.Popen(
                command,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(executable.parent),
            )
        except OSError as exc:
            raise ApplicationLaunchError(
                f"Failed to launch application '{spec.name}'."
            ) from exc

        return {
            "success": True,
            "status": "launched",
            "application": spec.name,
            "executable": str(executable),
            "pid": process.pid,
        }