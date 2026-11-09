
import os
import subprocess
import platform

from pathlib import Path
from typing import Any


class CommandExecutor:
    """Execute explicitly supported Windows commands."""

    TIMEOUT_SECONDS = 15
    MAX_OUTPUT_LENGTH = 50_000
    MAX_TREE_ENTRIES = 500
    MAX_TREE_DEPTH = 4

    # Only these fixed Windows executables can be launched.
    EXTERNAL_COMMANDS = {
        "TASKLIST": "tasklist.exe",
        "SYSTEMINFO": "systeminfo.exe",
        "DRIVERQUERY": "driverquery.exe",
    }

    @classmethod
    def execute(cls, command: list[str]) -> dict[str, Any]:
        """
        Execute a structured command.

        Expected input:
            ["DIR", "C:\\Users"]

        Returns:
            A structured execution result.
        """

        if not isinstance(command, list) or not command:
            return cls._error("Invalid command input.")

        if not all(isinstance(arg, str) for arg in command):
            return cls._error("Command arguments must be strings.")

        command_name = command[0].strip().upper()
        arguments = command[1:]

        try:
            # Dispatch only explicitly implemented commands.
            handlers = {
                "DIR": cls._dir,
                "CD": cls._cd,
                "CHDIR": cls._cd,
                "TREE": cls._tree,
                "VER": cls._version,
            }

            handler = handlers.get(command_name)

            if handler is not None:
                output = handler(arguments)
                return cls._success(output)

            if command_name in cls.EXTERNAL_COMMANDS:
                return cls._run_external(command_name, arguments)

            return cls._error(
                f"Command '{command_name}' has no executor implementation.",
                status="unsupported",
            )

        except FileNotFoundError:
            return cls._error("Requested path or executable was not found.")

        except PermissionError:
            return cls._error("Permission denied.")

        except subprocess.TimeoutExpired:
            return cls._error("Command execution timed out.")

        except OSError as exc:
            return cls._error(str(exc))

        except Exception as exc:
            return cls._error(
                f"{type(exc).__name__}: {exc}"
            )

    # -----------------------------------------------------
    # Built-in command handlers
    # -----------------------------------------------------

    @classmethod
    def _dir(cls, arguments: list[str]) -> str:
        """List files and directories."""

        if len(arguments) > 1:
            raise ValueError("DIR accepts at most one directory path.")

        path = cls._resolve_path(arguments[0] if arguments else ".")

        if not path.is_dir():
            raise ValueError("The specified path is not a directory.")

        entries = sorted(
            path.iterdir(),
            key=lambda entry: (not entry.is_dir(), entry.name.lower()),
        )

        lines = [f"Directory: {path}", ""]

        for entry in entries:
            entry_type = "<DIR>" if entry.is_dir() else "     "

            lines.append(
                f"{entry_type:6} {entry.name}"
            )

        lines.append("")
        lines.append(f"Total entries: {len(entries)}")

        return "\n".join(lines)

    @staticmethod
    def _cd(arguments: list[str]) -> str:
        """Display the current working directory."""

        if arguments:
            raise ValueError(
                "Changing the working directory is not supported yet."
            )

        return os.getcwd()

    @classmethod
    def _tree(cls, arguments: list[str]) -> str:
        """Display a bounded directory tree."""

        if len(arguments) > 1:
            raise ValueError("TREE accepts at most one directory path.")

        root = cls._resolve_path(arguments[0] if arguments else ".")

        if not root.is_dir():
            raise ValueError("The specified path is not a directory.")

        lines = [str(root)]
        count = 0

        def walk(directory: Path, depth: int):
            nonlocal count

            if depth >= cls.MAX_TREE_DEPTH:
                return

            try:
                entries = sorted(
                    directory.iterdir(),
                    key=lambda entry: entry.name.lower(),
                )
            except PermissionError:
                lines.append("    " * (depth + 1) + "[Access denied]")
                return

            for entry in entries:
                if count >= cls.MAX_TREE_ENTRIES:
                    lines.append("[Output limit reached]")
                    return

                count += 1

                prefix = "    " * (depth + 1)

                if entry.is_symlink():
                    lines.append(prefix + entry.name + " [LINK]")
                    continue

                if entry.is_dir():
                    lines.append(prefix + entry.name + "\\")
                    walk(entry, depth + 1)
                else:
                    lines.append(prefix + entry.name)

        walk(root, 0)

        return "\n".join(lines)

    @staticmethod
    def _version(arguments: list[str]) -> str:
        """Return Windows version information."""

        if arguments:
            raise ValueError("VER does not accept arguments.")

        if os.name != "nt":
            raise OSError("VER is only supported on Windows.")

        return f"Windows version: {platform.version()}"

    # -----------------------------------------------------
    # External executable handler
    # -----------------------------------------------------

    @classmethod
    def _run_external(
        cls,
        command_name: str,
        arguments: list[str],
    ) -> dict[str, Any]:
        """
        Execute a fixed, trusted Windows executable.

        No executable name or shell command is accepted from
        the LLM as an arbitrary process target.
        """

        if os.name != "nt":
            return cls._error("This command requires Windows.")

        # Initially, these commands run without additional arguments.
        # Command-specific argument support can be added later.
        if arguments:
            return cls._error(
                f"Arguments are not supported for {command_name} yet."
            )

        system_root = os.environ.get("SystemRoot")

        if not system_root:
            return cls._error("Windows SystemRoot is unavailable.")

        executable = (
            Path(system_root)
            / "System32"
            / cls.EXTERNAL_COMMANDS[command_name]
        )

        if not executable.is_file():
            return cls._error(
                f"Executable not found: {executable}"
            )

        # Pass only the minimal Windows environment required.
        safe_environment = {
            "SystemRoot": system_root,
            "WINDIR": system_root,
            "PATH": str(Path(system_root) / "System32"),
        }

        result = subprocess.run(
            [str(executable)],
            shell=False,
            capture_output=True,
            text=True,
            timeout=cls.TIMEOUT_SECONDS,
            check=False,
            cwd=system_root,
            env=safe_environment,
        )

        output = result.stdout or ""
        error = result.stderr or ""

        if result.returncode != 0:
            return cls._error(
                error.strip() or "Command returned a non-zero exit code.",
                status="execution_failed",
                exit_code=result.returncode,
            )

        return cls._success(
            output[:cls.MAX_OUTPUT_LENGTH],
            exit_code=result.returncode,
            truncated=len(output) > cls.MAX_OUTPUT_LENGTH,
        )

    # -----------------------------------------------------
    # Path validation
    # -----------------------------------------------------

    @staticmethod
    def _resolve_path(raw_path: str) -> Path:
        """Resolve an existing local filesystem path."""

        if not raw_path or not raw_path.strip():
            raise ValueError("Path cannot be empty.")

        if raw_path.startswith(("\\\\", "//")):
            raise ValueError("Network paths are not allowed.")

        if raw_path.startswith("\\\\?\\") or raw_path.startswith("\\\\.\\"):
            raise ValueError("Windows device paths are not allowed.")

        path = Path(raw_path).resolve(strict=True)

        return path

    # -----------------------------------------------------
    # Standard result helpers
    # -----------------------------------------------------

    @staticmethod
    def _success(
        output: str,
        *,
        exit_code: int = 0,
        truncated: bool = False,
    ) -> dict[str, Any]:

        return {
            "success": True,
            "status": "completed",
            "output": output,
            "exit_code": exit_code,
            "truncated": truncated,
        }

    @staticmethod
    def _error(
        message: str,
        *,
        status: str = "execution_failed",
        exit_code: int | None = None,
    ) -> dict[str, Any]:

        return {
            "success": False,
            "status": status,
            "output": "",
            "message": message,
            "exit_code": exit_code,
        }
