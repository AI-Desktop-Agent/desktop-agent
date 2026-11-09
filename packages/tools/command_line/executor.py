
import subprocess
from typing import Any


class CommandExecutor:

    @staticmethod
    def execute(command: list[str]) -> dict[str, Any]:
        try:
            process = subprocess.Popen(
                command,
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            return {
                "success": True,
                "process_id": process.pid,
                "message": "Command executed successfully."
            }

        except FileNotFoundError:
            return {
                "success": False,
                "message": "Executable not found."
            }

        except OSError as exc:
            return {
                "success": False,
                "message": str(exc)
            }
