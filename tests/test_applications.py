import asyncio

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from packages.agent_graph.builder import agent_graph
from packages.tools import TOOLS


async def chat_with_agent() -> None:
    tool_names = {agent_tool.name for agent_tool in TOOLS}

    if "open_application" not in tool_names:
        raise RuntimeError(
            "open_application is not registered with the agent graph."
        )

    if "command_line_tool" in tool_names:
        raise RuntimeError(
            "command_line_tool is still exposed to the agent graph."
        )

    print("Application integration test (LangGraph)")
    print("Ask the agent to open an allowlisted application.")
    print("Type 'exit' or 'quit' to stop.")

    messages = []

    while True:
        try:
            request = input("\nYou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nStopping application integration test.")
            break

        if not request:
            continue

        if request.lower() in {"exit", "quit"}:
            break

        next_messages = [*messages, HumanMessage(content=request)]

        try:
            result = await agent_graph.ainvoke(
                {"messages": next_messages},
                config={
                    "configurable": {
                        "thread_id": "application-integration-test",
                        "user_id": "local-user",
                    }
                },
            )
        except Exception as exc:
            print(f"Agent request failed: {type(exc).__name__}: {exc}")
            continue

        messages = result["messages"]
        response = messages[-1].content
        print(f"Agent> {response}")


def main() -> None:
    load_dotenv()
    asyncio.run(chat_with_agent())


if __name__ == "__main__":
    main()