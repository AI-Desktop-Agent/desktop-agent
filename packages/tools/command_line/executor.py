"""
command_executor.py

A constrained Windows command executor for a desktop agent.

Security boundaries:
- No shell is used.
- Only explicitly implemented commands are dispatched.
- Filesystem paths must resolve inside configured allowed roots.
- Symlinks and Windows reparse points are displayed but never traversed.
- Directory traversal, output, arguments, and process time are bounded.
- External executables are fixed absolute paths under Windows System32.
- File names are JSON-quoted and control characters are neutralized before
  being returned as tool output.

Important:
- Configure allowed roots once at trusted application startup.
- This is defense in depth, not a complete protection against a hostile
  process concurrently modifying the filesystem. Strong protection against
  filesystem TOCTOU races requires Windows handle-based traversal APIs.
- The agent's system prompt must still instruct the model to treat all tool
  output, including file names, as untrusted data rather than instructions.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import platform
import re
import stat
import subprocess
import threading

from pathlib import Path, PureWindowsPath
from typing import Any

logger = logging.getLogger(__name__)


class CommandRejected(Exception):
    """A request was refused by the executor."""


class _LimitReached(Exception):
    """Internal signal that the TREE entry budget has been exhausted."""


class CommandExecutor:
    """Execute a small, explicitly supported set of Windows commands."""

    # -----------------------------------------------------
    # Limits
    # -----------------------------------------------------

    TIMEOUT_SECONDS = 15
    COMMAND_TIMEOUTS = {"SYSTEMINFO": 60}
    MAX_OUTPUT_LENGTH = 50_000
    MAX_DIR_ENTRIES = 500
    MAX_TREE_ENTRIES = 500
    MAX_TREE_DEPTH = 4
    MAX_NAME_LENGTH = 120
    MAX_ARGUMENTS = 10
    MAX_ARGUMENT_LENGTH = 1_000
    READ_CHUNK_SIZE = 4_096
    OUTPUT_DRAIN_TIMEOUT_SECONDS = 3

    EXTERNAL_COMMANDS = {
        "TASKLIST": "tasklist.exe",
        "SYSTEMINFO": "systeminfo.exe",
        "DRIVERQUERY": "driverquery.exe",
    }

    _COMMAND_NAME = re.compile(r"^[A-Z][A-Z0-9]*$")
    _UNSAFE_CHARS = re.compile(
        r"[\x00-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2066-\u2069]"
    )

    # Set only through configure(), using trusted application configuration.
    _allowed_roots: tuple[Path, ...] = ()

    # -----------------------------------------------------
    # Configuration
    # -----------------------------------------------------

    @classmethod
    def configure(cls, allowed_roots: list[str]) -> None:
        """
        Configure filesystem roots the executor may read.

        Call this once during application startup. Until configured, all
        filesystem operations fail closed.
        """
        if not isinstance(allowed_roots, (list, tuple)) or not allowed_roots:
            raise ValueError("At least one allowed root is required.")

        resolved_roots: list[Path] = []

        for raw_root in allowed_roots:
            if not isinstance(raw_root, str) or not raw_root.strip():
                raise ValueError("Every allowed root must be a non-empty path.")

            # Parse Windows syntax even when unit tests run on another OS.
            windows_root = PureWindowsPath(raw_root.strip())

            # Reject UNC/device and drive-relative roots BEFORE any filesystem
            # operation. Configuration is trusted, but must still fail closed.
            if windows_root.drive.startswith("\\\\"):
                raise ValueError("Network and device folders cannot be roots.")

            if windows_root.drive and not windows_root.is_absolute():
                raise ValueError("Drive-relative roots are not allowed.")

            root_candidate = Path(raw_root.strip())
            root = root_candidate.resolve(strict=True)

            if not root.is_dir():
                raise ValueError(f"Allowed root is not a directory: {root}")

            if root.drive.startswith("\\\\"):
                raise ValueError("Network folders cannot be configured as roots.")

            # Do not allow an entire drive (e.g. C:\) as an allowed root.
            if root == Path(root.anchor):
                raise ValueError("A whole drive cannot be an allowed root.")

            resolved_roots.append(root)

        # Remove duplicates while preserving order.
        cls._allowed_roots = tuple(dict.fromkeys(resolved_roots))

    @classmethod
    def clear_configuration(cls) -> None:
        """Clear configured roots. Primarily useful for tests and shutdown."""
        cls._allowed_roots = ()

    @classmethod
    def _require_configured(cls) -> None:
        if not cls._allowed_roots:
            raise CommandRejected("No allowed folders are configured.")

    # -----------------------------------------------------
    # Entry point
    # -----------------------------------------------------

    @classmethod
    def execute(cls, command: list[str]) -> dict[str, Any]:
        """
        Execute a structured command.

        Examples:
            ["DIR", "."]
            ["TREE", "documents"]
            ["TASKLIST"]

        Returns a dictionary with a stable result schema.
        """
        if not isinstance(command, list) or not command:
            return cls._error(
                "Invalid command input.",
                status="invalid_arguments",
            )

        if not all(isinstance(argument, str) for argument in command):
            return cls._error(
                "Command arguments must be strings.",
                status="invalid_arguments",
            )

        if len(command) - 1 > cls.MAX_ARGUMENTS:
            return cls._error(
                "Too many arguments.",
                status="invalid_arguments",
            )

        if any(len(argument) > cls.MAX_ARGUMENT_LENGTH for argument in command):
            return cls._error(
                "An argument exceeds the maximum allowed length.",
                status="invalid_arguments",
            )

        command_name = command[0].strip().upper()
        arguments = command[1:]

        if not cls._COMMAND_NAME.fullmatch(command_name):
            return cls._error(
                "Invalid command name.",
                status="invalid_arguments",
            )

        try:
            handlers = {
                "DIR": cls._dir,
                "CD": cls._cd,
                "CHDIR": cls._cd,
                "TREE": cls._tree,
                "VER": cls._version,
            }

            handler = handlers.get(command_name)

            if handler is not None:
                handler_result = handler(arguments)
                if isinstance(handler_result, tuple):
                    output, was_truncated = handler_result
                    return cls._success(output, truncated=was_truncated)
                return cls._success(handler_result)

            if command_name in cls.EXTERNAL_COMMANDS:
                return cls._run_external(command_name, arguments)

            return cls._error(
                f"Command '{command_name}' has no executor implementation.",
                status="unsupported",
            )

        except CommandRejected as exc:
            return cls._error(str(exc), status="invalid_arguments")

        except FileNotFoundError:
            return cls._error("Path not found or not allowed.")

        except PermissionError:
            return cls._error("Permission denied.")

        except subprocess.TimeoutExpired:
            return cls._error("Command execution timed out.")

        except OSError:
            logger.exception("OS error while running %s", command_name)
            return cls._error("The operation could not be completed.")

        except Exception:
            logger.exception("Unexpected error while running %s", command_name)
            return cls._error("Internal error while running the command.")

    # -----------------------------------------------------
    # Built-in command handlers
    # -----------------------------------------------------

    @classmethod
    def _dir(cls, arguments: list[str]) -> tuple[str, bool]:
        """List at most MAX_DIR_ENTRIES from an allowed directory."""
        if len(arguments) > 1:
            raise CommandRejected("DIR accepts at most one directory path.")

        path = cls._resolve_path(arguments[0] if arguments else ".")

        if not path.is_dir():
            raise CommandRejected("The specified path is not a directory.")

        entries, truncated = cls._read_directory(path, cls.MAX_DIR_ENTRIES)

        labels = {
            "dir": "<DIR>",
            "link": "<LINK>",
            "file": "",
            "unknown": "<?>",
        }

        lines = [f"Directory: {path}", ""]

        for display_name, kind, _full_path in entries:
            lines.append(f"{labels[kind]:7} {display_name}")

        lines.append("")
        summary = f"Entries shown: {len(entries)}"
        if truncated:
            summary += " (additional entries omitted)"
        lines.append(summary)

        return "\n".join(lines), truncated

    @classmethod
    def _cd(cls, arguments: list[str]) -> str:
        """Display the executor's configured working directory."""
        if arguments:
            raise CommandRejected(
                "Changing the working directory is not supported."
            )

        cls._require_configured()
        return str(cls._allowed_roots[0])

    @classmethod
    def _tree(cls, arguments: list[str]) -> tuple[str, bool]:
        """Display a bounded directory tree without following links."""
        if len(arguments) > 1:
            raise CommandRejected("TREE accepts at most one directory path.")

        root = cls._resolve_path(arguments[0] if arguments else ".")

        if not root.is_dir():
            raise CommandRejected("The specified path is not a directory.")

        lines = [str(root)]
        remaining = cls.MAX_TREE_ENTRIES
        was_truncated = False

        def walk(directory: Path, depth: int) -> None:
            nonlocal remaining, was_truncated

            if depth >= cls.MAX_TREE_DEPTH:
                # Report truncation only when this directory actually has
                # children that cannot be displayed due to the depth limit.
                try:
                    children, more_children = cls._read_directory(directory, 1)
                    if children or more_children:
                        was_truncated = True
                except (CommandRejected, PermissionError, FileNotFoundError):
                    was_truncated = True
                return

            # Revalidate immediately before each directory read. This narrows
            # (but cannot completely eliminate) filesystem TOCTOU races.
            safe_directory = cls._resolve_path(str(directory))

            if not safe_directory.is_dir():
                return

            try:
                entries, truncated = cls._read_directory(
                    safe_directory,
                    remaining,
                )
            except PermissionError:
                lines.append("    " * (depth + 1) + "[Access denied]")
                return

            prefix = "    " * (depth + 1)

            for display_name, kind, full_path in entries:
                if remaining <= 0:
                    raise _LimitReached

                remaining -= 1

                if kind == "link":
                    lines.append(f"{prefix}{display_name} [LINK - not followed]")
                elif kind == "dir":
                    lines.append(f"{prefix}{display_name}\\")
                    walk(Path(full_path), depth + 1)
                else:
                    lines.append(prefix + display_name)

            if truncated:
                raise _LimitReached

        try:
            walk(root, 0)
        except _LimitReached:
            was_truncated = True
            lines.append("[Entry limit reached; remaining entries omitted]")
        except CommandRejected:
            # A directory may have changed or become inaccessible during
            # traversal. Do not continue into an unverified location.
            was_truncated = True
            lines.append("[Directory skipped: path no longer allowed or available]")

        return "\n".join(lines), was_truncated

    @staticmethod
    def _version(arguments: list[str]) -> str:
        """Return Windows version information without invoking a shell."""
        if arguments:
            raise CommandRejected("VER does not accept arguments.")

        if os.name != "nt":
            raise CommandRejected("VER is only supported on Windows.")

        return f"Windows version: {platform.version()}"

    # -----------------------------------------------------
    # Directory reading helpers
    # -----------------------------------------------------

    @classmethod
    def _safe_name(cls, name: str) -> str:
        """
        Neutralize control/bidi characters and JSON-quote the file name.

        Quoting improves the data boundary in tool output, but the LLM must
        still be instructed to treat tool output as untrusted data.
        """
        cleaned = cls._UNSAFE_CHARS.sub("?", name)

        if len(cleaned) > cls.MAX_NAME_LENGTH:
            cleaned = cleaned[: cls.MAX_NAME_LENGTH] + "..."

        return json.dumps(cleaned, ensure_ascii=True)

    @staticmethod
    def _entry_kind(entry: os.DirEntry) -> str:
        """
        Classify an entry without following symlinks/reparse points.

        Windows junctions and other reparse points are treated as links.
        """
        try:
            entry_stat = entry.stat(follow_symlinks=False)
            attributes = getattr(entry_stat, "st_file_attributes", 0)
            reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)

            if entry.is_symlink() or (
                reparse_attribute and attributes & reparse_attribute
            ):
                return "link"

            if entry.is_dir(follow_symlinks=False):
                return "dir"

            return "file"

        except OSError:
            return "unknown"

    @classmethod
    def _read_directory(
        cls,
        directory: Path,
        limit: int,
    ) -> tuple[list[tuple[str, str, str]], bool]:
        """
        Read no more than `limit` entries.

        Returns:
            (entries, truncated)

        Each entry is:
            (JSON-quoted display name, kind, original full path)
        """
        if limit <= 0:
            return [], True

        # Re-resolve immediately before scanning. This narrows the window in
        # which a concurrently replaced directory could escape the allowed
        # roots; it is not a substitute for handle-based traversal.
        directory = cls._resolve_path(str(directory))
        if not directory.is_dir():
            raise CommandRejected("The specified path is not a directory.")

        entries: list[tuple[str, str, str]] = []
        truncated = False

        with os.scandir(directory) as iterator:
            for entry in iterator:
                if len(entries) >= limit:
                    truncated = True
                    break

                entries.append(
                    (
                        cls._safe_name(entry.name),
                        cls._entry_kind(entry),
                        entry.path,
                    )
                )

        # Only the bounded set is sorted; the whole directory is never loaded.
        entries.sort(key=lambda item: (item[1] != "dir", item[0].lower()))

        return entries, truncated

    # -----------------------------------------------------
    # Windows API helpers
    # -----------------------------------------------------

    @staticmethod
    def _get_system_directory() -> str:
        """Get the actual Windows system directory without trusting env vars."""
        if os.name != "nt":
            raise OSError("Windows is required.")

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_system_directory = kernel32.GetSystemDirectoryW
        get_system_directory.argtypes = [
            ctypes.POINTER(ctypes.c_wchar),
            ctypes.c_uint,
        ]
        get_system_directory.restype = ctypes.c_uint

        buffer = ctypes.create_unicode_buffer(32_768)
        length = get_system_directory(buffer, len(buffer))

        if length == 0 or length >= len(buffer):
            error_code = ctypes.get_last_error()
            raise OSError(error_code, "Could not determine Windows system directory.")

        return buffer.value

    @staticmethod
    def _get_oem_encoding() -> str:
        """Return the Windows OEM code page as a Python codec name."""
        if os.name != "nt":
            return "utf-8"

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        get_oem_cp = kernel32.GetOEMCP
        get_oem_cp.argtypes = []
        get_oem_cp.restype = ctypes.c_uint

        code_page = get_oem_cp()
        if not code_page:
            raise OSError("Could not determine Windows OEM code page.")

        return f"cp{code_page}"

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
        Run one fixed System32 executable without a shell.

        Output is read by bounded reader threads. This avoids capturing an
        unlimited stdout/stderr buffer in memory while still draining both
        pipes to prevent the child process from blocking.
        """
        if os.name != "nt":
            return cls._error("This command requires Windows.")

        if arguments:
            return cls._error(
                f"Arguments are not supported for {command_name} yet.",
                status="invalid_arguments",
            )

        # Do not trust environment variables to locate executables. Ask
        # Windows for its actual system directory (System32 or SysWOW64).
        system_directory = Path(cls._get_system_directory()).resolve(strict=True)

        if (
            not system_directory.is_dir()
            or system_directory.drive.startswith("\\\\")
        ):
            return cls._error("Windows system directory is invalid.")

        executable_name = cls.EXTERNAL_COMMANDS[command_name]
        executable = (system_directory / executable_name).resolve(strict=True)

        if executable.parent != system_directory or not executable.is_file():
            return cls._error("Approved executable was not found.")

        windows_directory = system_directory.parent
        safe_environment = {
            "SystemRoot": str(windows_directory),
            "WINDIR": str(windows_directory),
            "PATH": str(system_directory),
        }

        process = subprocess.Popen(
            [str(executable)],
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(system_directory),
            env=safe_environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        stdout_buffer = bytearray()
        stderr_buffer = bytearray()
        stdout_truncated = threading.Event()
        stderr_truncated = threading.Event()

        def drain_stream(
            stream: Any,
            buffer: bytearray,
            truncated_event: threading.Event,
        ) -> None:
            try:
                while True:
                    chunk = stream.read(cls.READ_CHUNK_SIZE)
                    if not chunk:
                        break

                    remaining_bytes = cls.MAX_OUTPUT_LENGTH - len(buffer)
                    if remaining_bytes > 0:
                        buffer.extend(chunk[:remaining_bytes])

                    if len(chunk) > max(remaining_bytes, 0):
                        truncated_event.set()
            except (OSError, ValueError):
                logger.exception("Failed while reading command output stream")
            finally:
                try:
                    stream.close()
                except OSError:
                    pass

        stdout_thread = threading.Thread(
            target=drain_stream,
            args=(process.stdout, stdout_buffer, stdout_truncated),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=drain_stream,
            args=(process.stderr, stderr_buffer, stderr_truncated),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        timeout = cls.COMMAND_TIMEOUTS.get(
            command_name,
            cls.TIMEOUT_SECONDS,
        )

        try:
            return_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            # A descendant could inherit a pipe handle. Never let a reader
            # thread keep the agent stuck indefinitely after the timeout.
            stdout_thread.join(timeout=cls.OUTPUT_DRAIN_TIMEOUT_SECONDS)
            stderr_thread.join(timeout=cls.OUTPUT_DRAIN_TIMEOUT_SECONDS)
            return cls._error(
                "Command execution timed out.",
                status="timeout",
            )

        stdout_thread.join(timeout=cls.OUTPUT_DRAIN_TIMEOUT_SECONDS)
        stderr_thread.join(timeout=cls.OUTPUT_DRAIN_TIMEOUT_SECONDS)

        if stdout_thread.is_alive() or stderr_thread.is_alive():
            logger.warning(
                "Output pipes for %s did not close after the process exited",
                command_name,
            )
            return cls._error(
                "Command finished, but output collection did not complete.",
                status="output_incomplete",
                exit_code=return_code,
                truncated=True,
            )

        # Windows console utilities generally emit text in the OEM code page.
        # Ask Windows for the active OEM code page; 'oem' is not a portable
        # Python codec name.
        output_encoding = cls._get_oem_encoding()
        stdout = bytes(stdout_buffer).decode(output_encoding, errors="replace")
        stderr = bytes(stderr_buffer).decode(output_encoding, errors="replace")

        if return_code != 0:
            message = stderr.strip()[:500] or (
                "Command returned a non-zero exit code."
            )
            return cls._error(
                message,
                status="execution_failed",
                exit_code=return_code,
                truncated=stderr_truncated.is_set(),
            )

        output = stdout if stdout else stderr
        return cls._success(
            output,
            exit_code=return_code,
            truncated=(
                stdout_truncated.is_set()
                or stderr_truncated.is_set()
            ),
        )

    # -----------------------------------------------------
    # Path validation
    # -----------------------------------------------------

    @classmethod
    def _assert_no_link_components(cls, root: Path, candidate: Path) -> None:
        """
        Reject symlink/reparse-point components from root to candidate.

        This is a best-effort path-based check. A hostile concurrent process
        can still race it; handle-based traversal is needed to close that gap.
        """
        if not candidate.is_relative_to(root):
            raise CommandRejected("Path not found or not allowed.")

        components = [root]
        current = root
        for part in candidate.relative_to(root).parts:
            current = current / part
            components.append(current)

        for index, component in enumerate(components):
            try:
                metadata = component.lstat()
                attributes = getattr(metadata, "st_file_attributes", 0)
                reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)

                if stat.S_ISLNK(metadata.st_mode) or (
                    reparse_flag and attributes & reparse_flag
                ):
                    raise CommandRejected(
                        "Symbolic links and junctions are not allowed."
                    )

                is_last = index == len(components) - 1
                if not is_last and not stat.S_ISDIR(metadata.st_mode):
                    raise CommandRejected("A path component is not a directory.")
            except FileNotFoundError:
                raise CommandRejected("Path not found or not allowed.") from None

    @classmethod
    def _resolve_path(cls, raw_path: str) -> Path:
        """
        Resolve an existing path inside an allowed root without traversing
        symlink/reparse-point components.

        Relative paths are interpreted relative to the first configured root.
        """
        cls._require_configured()

        if not isinstance(raw_path, str) or not raw_path.strip():
            raise CommandRejected("Path cannot be empty.")

        raw_path = raw_path.strip()
        if "\x00" in raw_path:
            raise CommandRejected("Invalid path.")

        # Parse Windows path syntax independent of the host OS. This catches
        # UNC/device paths and drive-relative forms before filesystem access.
        windows_path = PureWindowsPath(raw_path)

        if windows_path.drive.startswith("\\\\"):
            raise CommandRejected("Network and device paths are not allowed.")

        if windows_path.drive and not windows_path.is_absolute():
            raise CommandRejected("Drive-relative paths are not allowed.")

        if ".." in windows_path.parts:
            raise CommandRejected("Parent-directory traversal is not allowed.")

        # Reject alternate data streams (e.g. file.txt:secret).
        windows_parts = windows_path.parts[1:] if windows_path.anchor else windows_path.parts
        if any(":" in part for part in windows_parts):
            raise CommandRejected("Colons are not allowed in paths.")

        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = cls._allowed_roots[0] / candidate

        # Normalize lexical components without resolving links.
        candidate = Path(os.path.abspath(candidate))

        matching_roots = [
            root for root in cls._allowed_roots
            if candidate == root or candidate.is_relative_to(root)
        ]
        if not matching_roots:
            raise CommandRejected("Path not found or not allowed.")

        # Use the most specific matching root if roots are nested.
        root = max(matching_roots, key=lambda item: len(item.parts))

        cls._assert_no_link_components(root, candidate)

        # Re-resolve after the no-link walk and verify containment again.
        # This narrows races but does not eliminate concurrent replacement.
        try:
            resolved = candidate.resolve(strict=True)
        except (FileNotFoundError, RuntimeError):
            raise CommandRejected("Path not found or not allowed.") from None

        if resolved != candidate or not (
            resolved == root or resolved.is_relative_to(root)
        ):
            raise CommandRejected("Path not found or not allowed.")

        return resolved

    # -----------------------------------------------------
    # Standard result helpers
    # -----------------------------------------------------

    @classmethod
    def _success(
        cls,
        output: str,
        *,
        exit_code: int = 0,
        truncated: bool = False,
    ) -> dict[str, Any]:
        """Apply a common output limit to every successful handler."""
        if len(output) > cls.MAX_OUTPUT_LENGTH:
            output = output[: cls.MAX_OUTPUT_LENGTH]
            truncated = True

        return {
            "success": True,
            "status": "completed",
            "output": output,
            "message": "",
            "exit_code": exit_code,
            "truncated": truncated,
        }

    @staticmethod
    def _error(
        message: str,
        *,
        status: str = "execution_failed",
        exit_code: int | None = None,
        truncated: bool = False,
    ) -> dict[str, Any]:
        return {
            "success": False,
            "status": status,
            "output": "",
            "message": message,
            "exit_code": exit_code,
            "truncated": truncated,
        }
