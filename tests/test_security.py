
import unittest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, ToolMessage

from packages.agent_graph.nodes.tool_node import secure_tool_node
from packages.security.policy import Denied


class TestSecureToolNode(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.tool_call = {
            "name": "web_search",
            "args": {"query": "Python programming"},
            "id": "call-123",
            "type": "tool_call",
        }

        self.state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[self.tool_call],
                )
            ]
        }

        self.config = {
            "configurable": {
                "thread_id": "session-123",
                "user_id": "user-123",
            }
        }

    @patch("packages.agent_graph.nodes.tool_node.gateway.execute",
           new_callable=AsyncMock)
    @patch("packages.agent_graph.nodes.tool_node.taint_tracker.is_tainted")
    async def test_successful_tool_execution(
        self, mock_is_tainted, mock_execute
    ):
        mock_is_tainted.return_value = False
        mock_execute.return_value = "Search results"

        result = await secure_tool_node(self.state, self.config)

        mock_execute.assert_awaited_once_with(
            "web_search",
            {"query": "Python programming"},
            principal="user-123",
            granted_scopes=(),
            tainted=False,
            context_id="session-123",
        )

        message = result["messages"][0]

        self.assertIsInstance(message, ToolMessage)
        self.assertEqual(message.content, "Search results")
        self.assertEqual(message.tool_call_id, "call-123")
        self.assertEqual(message.name, "web_search")

    @patch("packages.agent_graph.nodes.tool_node.gateway.execute",
           new_callable=AsyncMock)
    @patch("packages.agent_graph.nodes.tool_node.taint_tracker.is_tainted")
    async def test_tainted_context_is_forwarded(
        self, mock_is_tainted, mock_execute
    ):
        mock_is_tainted.return_value = True
        mock_execute.return_value = "Search results"

        await secure_tool_node(self.state, self.config)

        self.assertTrue(
            mock_execute.await_args.kwargs["tainted"]
        )

    @patch("packages.agent_graph.nodes.tool_node.gateway.execute",
           new_callable=AsyncMock)
    @patch("packages.agent_graph.nodes.tool_node.taint_tracker.is_tainted")
    async def test_denied_tool_returns_tool_message(
        self, mock_is_tainted, mock_execute
    ):
        mock_is_tainted.return_value = False
        mock_execute.side_effect = Denied("missing required scopes")

        result = await secure_tool_node(self.state, self.config)

        message = result["messages"][0]

        self.assertIsInstance(message, ToolMessage)
        self.assertIn("Tool blocked by security policy", message.content)
        self.assertEqual(message.tool_call_id, "call-123")

    @patch("packages.agent_graph.nodes.tool_node.gateway.execute",
           new_callable=AsyncMock)
    @patch("packages.agent_graph.nodes.tool_node.taint_tracker.is_tainted")
    async def test_unexpected_error_returns_tool_message(
        self, mock_is_tainted, mock_execute
    ):
        mock_is_tainted.return_value = False
        mock_execute.side_effect = RuntimeError("audit failure")

        result = await secure_tool_node(self.state, self.config)

        message = result["messages"][0]

        self.assertIsInstance(message, ToolMessage)
        self.assertIn("RuntimeError", message.content)
        self.assertIn("Do not automatically retry", message.content)

    @patch("packages.agent_graph.nodes.tool_node.gateway.execute",
           new_callable=AsyncMock)
    @patch("packages.agent_graph.nodes.tool_node.taint_tracker.is_tainted")
    async def test_multiple_tool_calls_are_executed(
        self, mock_is_tainted, mock_execute
    ):
        second_call = {
            "name": "web_search",
            "args": {"query": "LangGraph"},
            "id": "call-456",
            "type": "tool_call",
        }

        self.state["messages"][-1].tool_calls.append(second_call)

        mock_is_tainted.return_value = False
        mock_execute.side_effect = ["First result", "Second result"]

        result = await secure_tool_node(self.state, self.config)

        self.assertEqual(mock_execute.await_count, 2)
        self.assertEqual(len(result["messages"]), 2)

        self.assertEqual(
            [message.tool_call_id for message in result["messages"]],
            ["call-123", "call-456"],
        )

    @patch("packages.agent_graph.nodes.tool_node.gateway.execute",
           new_callable=AsyncMock)
    @patch("packages.agent_graph.nodes.tool_node.taint_tracker.is_tainted")
    async def test_default_context_is_used_when_config_missing(
        self, mock_is_tainted, mock_execute
    ):
        mock_is_tainted.return_value = False
        mock_execute.return_value = "Search results"

        await secure_tool_node(
            self.state,
            {"configurable": {}},
        )

        self.assertEqual(
            mock_execute.await_args.kwargs["context_id"],
            "default-session",
        )

        self.assertEqual(
            mock_execute.await_args.kwargs["principal"],
            "local-user",
        )


if __name__ == "__main__":
    unittest.main()
