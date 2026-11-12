import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from packages.llm.remote_ollama_provider import RemoteOllamaLLM


@patch("packages.llm.remote_ollama_provider.ChatOpenAI")
def test_async_invoke_after_binding_tools(mock_chat_openai):
    expected_response = MagicMock()

    bound_model = MagicMock()
    bound_model.ainvoke = AsyncMock(return_value=expected_response)

    mock_chat_openai.return_value.bind_tools.return_value = bound_model

    provider = RemoteOllamaLLM(
        model_name="test-model",
        base_url="http://127.0.0.1:8000/v1",
        api_key="test-key",
    )

    llm_with_tools = provider.bind_tools([])

    result = asyncio.run(llm_with_tools.ainvoke("Hello"))

    bound_model.ainvoke.assert_awaited_once_with("Hello")
    assert result is expected_response