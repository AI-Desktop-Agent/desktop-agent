
import asyncio
import time

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

from packages.agent_graph.builder import agent_graph
from packages.tools.search.web_search import web_search
from packages.core.runtime.agent_runtime import AgentRuntime
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------
# Test 1: Actual agent graph - async LLM response
# --------------------------------------------------

async def test_async_agent_response():
    print("\n[TEST 1] Async agent response")

    result = await agent_graph.ainvoke({
        "messages": [
            {"role": "user", "content": "Hello! Introduce yourself briefly."}
        ]
    })

    response = result["messages"][-1].content

    assert response, "Agent returned an empty response"

    print("Agent response:", response)
    print("[PASS] Async agent response")


# --------------------------------------------------
# Test 2: Actual asynchronous web search tool
# --------------------------------------------------

async def test_async_web_search():
    print("\n[TEST 2] Async web search")

    result = await web_search.ainvoke({
        "query": "Python programming language"
    })

    assert isinstance(result, str)
    assert result.strip(), "Web search returned an empty result"

    print("Search result:", result[:300])
    print("[PASS] Async web search")


# --------------------------------------------------
# Test 3: Parallel execution of multiple tools
# --------------------------------------------------

@tool
async def slow_tool(value: int) -> str:
    """Wait for two seconds and return the supplied value."""
    await asyncio.sleep(2)
    return f"Result: {value}"


async def test_parallel_tool_execution():
    print("\n[TEST 3] Parallel tool execution")

    builder = StateGraph(MessagesState)

    builder.add_node("tools", ToolNode([slow_tool]))
    builder.add_edge(START, "tools")
    builder.add_edge("tools", END)

    graph = builder.compile()

    message = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "slow_tool",
                "args": {"value": 1},
                "id": "call_1",
                "type": "tool_call",
            },
            {
                "name": "slow_tool",
                "args": {"value": 2},
                "id": "call_2",
                "type": "tool_call",
            },
        ],
    )

    start = time.perf_counter()

    result = await graph.ainvoke({
        "messages": [message]
    })

    elapsed = time.perf_counter() - start

    tool_results = result["messages"][1:]

    assert len(tool_results) == 2
    assert elapsed < 3.5, (
        f"Expected parallel execution, but took {elapsed:.2f} seconds"
    )

    print("Tool results:", [msg.content for msg in tool_results])
    print(f"Execution time: {elapsed:.2f} seconds")
    print("[PASS] Parallel tool execution")


# --------------------------------------------------
# Test 4: Runtime async bridge
# --------------------------------------------------

async def test_runtime_async_execution():
    print("\n[TEST 4] Runtime async execution")

    runtime = AgentRuntime(
        graph=agent_graph,
        stt=None,
        recorder=None,
        tts=None,
    )

    response = await runtime._process_text_async(
        "What is Python? Answer in one sentence."
    )

    assert isinstance(response, str)
    assert response.strip()

    print("Runtime response:", response)
    print("[PASS] Runtime async execution")

# --------------------------------------------------
# Test runner
# --------------------------------------------------

async def run_async_tests():
    await test_async_agent_response()
    await test_async_web_search()
    await test_parallel_tool_execution()
    await test_runtime_async_execution()

def main():
    try:
        asyncio.run(run_async_tests())

        # Runtime bridge uses asyncio.run internally.
        # Therefore, call it outside the running event loop.
        # test_runtime_async_bridge()

        print("\n================================")
        print("ALL ASYNC TESTS PASSED")
        print("================================")

    except Exception as exc:
        print("\n[FAILED]", repr(exc))
        raise


if __name__ == "__main__":
    main()
    