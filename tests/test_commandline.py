import asyncio
import json
import os

from dotenv import load_dotenv

from packages.tools.command_line.command_line_tool import command_line_tool
from packages.tools.command_line.executor import CommandExecutor


DEFAULT_ALLOWED_ROOT = (
    r"C:\Users\Manpreet Singh\OneDrive\Desktop\desktop agent test dir"
)


def get_allowed_roots() -> list[str]:
    configured_roots = os.getenv("DESKTOP_AGENT_ALLOWED_ROOTS")

    if configured_roots:
        return [
            root.strip()
            for root in configured_roots.split(";")
            if root.strip()
        ]

    return [DEFAULT_ALLOWED_ROOT]


def configure_executor() -> list[str]:
    allowed_roots = get_allowed_roots()
    CommandExecutor.configure(allowed_roots)
    return allowed_roots


async def run_command_request(request: str) -> dict:
    return await command_line_tool.ainvoke({"request": request})


async def run_chat_loop(allowed_roots: list[str]) -> None:
    print("Command-line chat test")
    print("Allowed folders:")
    for root in allowed_roots:
        print(f"  - {root}")
    print("Type 'exit' or 'quit' to stop.")

    while True:
        try:
            request = input("\nCommand> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nStopping command-line test.")
            break

        if not request:
            continue

        if request.lower() in {"exit", "quit"}:
            break

        try:
            result = await run_command_request(request)
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "success": False,
                        "status": "error",
                        "message": f"{type(exc).__name__}: {exc}",
                    },
                    indent=2,
                )
            )
            continue

        print(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    load_dotenv()
    allowed_roots = configure_executor()
    asyncio.run(run_chat_loop(allowed_roots))


if __name__ == "__main__":
    main()
