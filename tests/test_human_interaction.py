import asyncio
import io
from contextlib import redirect_stdout
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command, interrupt

from packages.agent_graph.builder import agent_graph
from packages.core.runtime.console_human_interaction import (
    ConsoleHumanInteraction,
    HumanInputUnavailable,
)
from packages.llm.llm_manager import llm_manager
from packages.security.gateway import gateway


class FakeBoundChatModel:
    async def ainvoke(self, messages):
        last_message = messages[-1]

        if isinstance(last_message, HumanMessage):
            request = last_message.content.lower()

            if "open browser" in request:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "ask_clarification",
                            "args": {
                                "question": "Which browser should I open?",
                                "options": ["Chrome", "Edge"],
                            },
                            "id": "clarification-1",
                            "type": "tool_call",
                        }
                    ],
                )

            if "open chrome" in request:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "open_application",
                            "args": {
                                "application": "chrome",
                                "arguments": ["https://example.com"],
                            },
                            "id": "application-1",
                            "type": "tool_call",
                        }
                    ],
                )

        if isinstance(last_message, ToolMessage):
            if last_message.name == "ask_clarification":
                return AIMessage(
                    content="The browser choice is confirmed."
                )

            if "blocked" in last_message.content.lower():
                return AIMessage(
                    content="The application launch was denied."
                )

            return AIMessage(
                content="The application launch was approved."
            )

        return AIMessage(content="I could not determine the requested action.")


class FakeChatModel:
    def bind_tools(self, tools):
        return FakeBoundChatModel()


class TestConsoleHumanInteraction(IsolatedAsyncioTestCase):
    async def test_langraph_clarification_interrupt_and_resume(self):
        config = {
            "configurable": {
                "thread_id": "hitl-clarification-test",
                "user_id": "local-user",
            }
        }

        with patch.object(
            llm_manager,
            "get_chat_llm",
            return_value=FakeChatModel(),
        ):
            paused = await agent_graph.ainvoke(
                {"messages": [HumanMessage(content="Open browser")]},
                config=config,
            )

            self.assertIn("__interrupt__", paused)
            interruptions = paused["__interrupt__"]
            self.assertEqual(len(interruptions), 1)
            payload = interruptions[0].value
            self.assertEqual(payload["kind"], "clarification")
            self.assertEqual(
                payload["prompt"],
                "Which browser should I open?",
            )
            self.assertEqual(payload["options"], ["Chrome", "Edge"])

            resumed = await agent_graph.ainvoke(
                Command(resume="Chrome"),
                config=config,
            )

        final_message = resumed["messages"][-1]
        self.assertIsInstance(final_message, AIMessage)
        self.assertEqual(
            final_message.content,
            "The browser choice is confirmed.",
        )

    async def test_langgraph_high_risk_approval_denies_launch(self):
        config = {
            "configurable": {
                "thread_id": "hitl-denial-test",
                "user_id": "local-user",
            }
        }
        previous_callback = gateway._approval_callback

        def approval_callback(tool_name, risk, args, principal):
            return interrupt(
                {
                    "kind": "approval",
                    "prompt": "Approve this application launch?",
                    "options": ["approve", "deny"],
                }
            )

        gateway.set_approval_callback(approval_callback)

        try:
            with (
                patch.object(
                    llm_manager,
                    "get_chat_llm",
                    return_value=FakeChatModel(),
                ),
                patch(
                    "packages.tools.applications.application_launcher."
                    "ApplicationLauncher.launch"
                ) as launch,
            ):
                paused = await agent_graph.ainvoke(
                    {
                        "messages": [
                            HumanMessage(content="Open Chrome")
                        ]
                    },
                    config=config,
                )

                payload = paused["__interrupt__"][0].value
                self.assertEqual(payload["kind"], "approval")
                self.assertEqual(
                    payload["options"],
                    ["approve", "deny"],
                )

                resumed = await agent_graph.ainvoke(
                    Command(resume=False),
                    config=config,
                )

            launch.assert_not_called()
            final_message = resumed["messages"][-1]
            self.assertIsInstance(final_message, AIMessage)
            self.assertEqual(
                final_message.content,
                "The application launch was denied.",
            )
        finally:
            gateway.set_approval_callback(previous_callback)

    async def test_langgraph_high_risk_approval_launches_after_approve(self):
        config = {
            "configurable": {
                "thread_id": "hitl-approval-test",
                "user_id": "local-user",
            }
        }
        previous_callback = gateway._approval_callback

        def approval_callback(tool_name, risk, args, principal):
            return interrupt(
                {
                    "kind": "approval",
                    "prompt": "Approve this application launch?",
                    "options": ["approve", "deny"],
                }
            )

        gateway.set_approval_callback(approval_callback)
        launch_result = {
            "success": True,
            "status": "launched",
            "application": "chrome",
            "executable": "C:\\Program Files\\Google\\Chrome\\chrome.exe",
            "pid": 1234,
        }

        try:
            with (
                patch.object(
                    llm_manager,
                    "get_chat_llm",
                    return_value=FakeChatModel(),
                ),
                patch(
                    "packages.tools.applications.application_launcher."
                    "ApplicationLauncher.launch",
                    return_value=launch_result,
                ) as launch,
            ):
                paused = await agent_graph.ainvoke(
                    {
                        "messages": [
                            HumanMessage(content="Open Chrome")
                        ]
                    },
                    config=config,
                )

                self.assertEqual(
                    paused["__interrupt__"][0].value["kind"],
                    "approval",
                )

                resumed = await agent_graph.ainvoke(
                    Command(resume=True),
                    config=config,
                )

            launch.assert_called_once_with(
                application="chrome",
                arguments=["https://example.com"],
            )
            final_message = resumed["messages"][-1]
            self.assertIsInstance(final_message, AIMessage)
            self.assertEqual(
                final_message.content,
                "The application launch was approved.",
            )
        finally:
            gateway.set_approval_callback(previous_callback)

    async def test_approval_requires_exact_approval(self):
        interaction = ConsoleHumanInteraction()

        with patch("builtins.input", return_value="approve"):
            self.assertTrue(
                await interaction.request_approval(
                    "open_application",
                    "high",
                    {"application": "chrome"},
                    "local-user",
                )
            )

        with patch("builtins.input", return_value="yes"):
            self.assertFalse(
                await interaction.request_approval(
                    "open_application",
                    "high",
                    {"application": "chrome"},
                    "local-user",
                )
            )

    async def test_unavailable_approval_input_denies(self):
        interaction = ConsoleHumanInteraction()

        with patch("builtins.input", side_effect=EOFError):
            approved = await interaction.request_approval(
                "open_application",
                "high",
                {"application": "chrome"},
                "local-user",
            )

        self.assertFalse(approved)

    async def test_approval_display_redacts_sensitive_arguments(self):
        interaction = ConsoleHumanInteraction()
        output = io.StringIO()

        with (
            patch("builtins.input", return_value="deny"),
            redirect_stdout(output),
        ):
            approved = await interaction.request_approval(
                "open_application",
                "high",
                {
                    "application": "chrome",
                    "api_key": "do-not-display",
                },
                "local-user",
            )

        self.assertFalse(approved)
        self.assertNotIn("do-not-display", output.getvalue())
        self.assertIn("[REDACTED]", output.getvalue())

    async def test_approval_display_redacts_url_credentials(self):
        interaction = ConsoleHumanInteraction()
        output = io.StringIO()

        with (
            patch("builtins.input", return_value="deny"),
            redirect_stdout(output),
        ):
            await interaction.request_approval(
                "open_application",
                "high",
                {"url": "https://user:password@example.com/?api_key=secret-value"},
                "local-user",
            )

        rendered = output.getvalue()
        self.assertNotIn("user:password", rendered)
        self.assertNotIn("secret-value", rendered)

    async def test_clarification_accepts_listed_option(self):
        interaction = ConsoleHumanInteraction()

        with patch("builtins.input", return_value="2"):
            answer = await interaction.ask_clarification(
                "Which browser should I open?",
                ("Chrome", "Edge"),
            )

        self.assertEqual(answer, "Edge")

    async def test_clarification_retries_invalid_choice(self):
        interaction = ConsoleHumanInteraction()

        with patch("builtins.input", side_effect=["Firefox", "1"]):
            answer = await interaction.ask_clarification(
                "Choose a browser.",
                ("Chrome", "Edge"),
            )

        self.assertEqual(answer, "Chrome")

    async def test_clarification_reports_unavailable_input(self):
        interaction = ConsoleHumanInteraction()

        with patch("builtins.input", side_effect=EOFError):
            with self.assertRaises(HumanInputUnavailable):
                await interaction.ask_clarification("What should I open?")


async def chat_with_langgraph() -> None:
    interaction = ConsoleHumanInteraction()
    thread_id = "human-interaction-chat"
    config = {
        "configurable": {
            "thread_id": thread_id,
            "user_id": "local-user",
        }
    }
    previous_callback = gateway._approval_callback

    def graph_approval_callback(tool_name, risk, args, principal):
        prompt = "\n".join(
            (
                "Approve this tool action?",
                f"Tool: {tool_name}",
                f"Risk: {risk}",
                f"User: {principal}",
            )
        )
        return interrupt(
            {
                "kind": "approval",
                "prompt": prompt,
                "options": ["approve", "deny"],
            }
        )

    gateway.set_approval_callback(graph_approval_callback)

    print("LangGraph human-in-the-loop chat")
    print("Ask a question or request an application.")
    print("Type 'exit' or 'quit' to stop.")

    try:
        while True:
            try:
                request = input("\nYou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nStopping LangGraph chat.")
                break

            if not request:
                continue

            if request.lower() in {"exit", "quit"}:
                break

            try:
                result = await agent_graph.ainvoke(
                    {"messages": [HumanMessage(content=request)]},
                    config=config,
                )

                while result.get("__interrupt__"):
                    interruptions = result["__interrupt__"]
                    if len(interruptions) != 1:
                        raise RuntimeError(
                            "Only one human interaction can be active at a time."
                        )

                    payload = interruptions[0].value
                    kind = payload.get("kind")
                    prompt = payload.get("prompt")
                    options = payload.get("options", [])

                    if kind not in {"clarification", "approval"}:
                        raise RuntimeError(
                            "LangGraph returned an unsupported human request."
                        )

                    answer = await interaction.ask_clarification(
                        prompt,
                        options,
                    )
                    resume_value = (
                        answer.casefold() == "approve"
                        if kind == "approval"
                        else answer
                    )

                    result = await agent_graph.ainvoke(
                        Command(resume=resume_value),
                        config=config,
                    )

                final_message = result["messages"][-1]
                print(f"Agent> {final_message.content}")

            except HumanInputUnavailable:
                print("Unable to collect a human response. Continuing stopped.")
                break
            except Exception as exc:
                print(f"Agent request failed: {type(exc).__name__}: {exc}")
    finally:
        gateway.set_approval_callback(previous_callback)


def main() -> None:
    load_dotenv()
    asyncio.run(chat_with_langgraph())


if __name__ == "__main__":
    main()
