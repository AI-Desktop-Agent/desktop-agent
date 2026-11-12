
import pytest
from unittest.mock import MagicMock, patch

from packages.llm.remote_ollama_provider import RemoteOllamaLLM


class TestRemoteOllamaLLM:

    def setup_method(self):
        self.model = "test-model"
        self.base_url = "http://100.72.240.94:8000/v1"
        self.api_key = "test-api-key"

    def test_load_configuration_from_environment(self, monkeypatch):
        monkeypatch.setenv("REMOTE_OLLAMA_MODEL", self.model)
        monkeypatch.setenv("REMOTE_OLLAMA_BASE_URL", self.base_url)
        monkeypatch.setenv("REMOTE_OLLAMA_API_KEY", self.api_key)

        llm = RemoteOllamaLLM()

        assert llm.model_name == self.model
        assert llm.base_url == self.base_url
        assert llm.api_key == self.api_key

    def test_explicit_configuration_overrides_environment(self, monkeypatch):
        monkeypatch.setenv("REMOTE_OLLAMA_MODEL", "environment-model")
        monkeypatch.setenv("REMOTE_OLLAMA_BASE_URL", "http://localhost:8000/v1")
        monkeypatch.setenv("REMOTE_OLLAMA_API_KEY", "environment-key")

        llm = RemoteOllamaLLM(
            model_name=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
        )

        assert llm.model_name == self.model
        assert llm.base_url == self.base_url
        assert llm.api_key == self.api_key

    @pytest.mark.parametrize(
        "missing_variable, error_message",
        [
            ("REMOTE_OLLAMA_MODEL", "REMOTE_OLLAMA_MODEL is not configured"),
            ("REMOTE_OLLAMA_BASE_URL", "REMOTE_OLLAMA_BASE_URL is not configured"),
            ("REMOTE_OLLAMA_API_KEY", "REMOTE_OLLAMA_API_KEY is not configured"),
        ],
    )
    def test_missing_configuration_raises_error(
        self, monkeypatch, missing_variable, error_message
    ):
        monkeypatch.setenv("REMOTE_OLLAMA_MODEL", self.model)
        monkeypatch.setenv("REMOTE_OLLAMA_BASE_URL", self.base_url)
        monkeypatch.setenv("REMOTE_OLLAMA_API_KEY", self.api_key)

        monkeypatch.delenv(missing_variable)

        llm = RemoteOllamaLLM()

        with pytest.raises(ValueError, match=error_message):
            llm.initialize_client()

    @patch("packages.llm.remote_ollama_llm.ChatOpenAI")
    def test_initialize_client(self, mock_chat_openai):
        llm = RemoteOllamaLLM(
            model_name=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
        )

        llm.initialize_client()

        mock_chat_openai.assert_called_once_with(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=0.2,
            max_retries=2,
        )

        assert llm.client is mock_chat_openai.return_value

    @patch("packages.llm.remote_ollama_llm.ChatOpenAI")
    def test_invoke(self, mock_chat_openai):
        expected_response = MagicMock()
        mock_client = mock_chat_openai.return_value
        mock_client.invoke.return_value = expected_response

        llm = RemoteOllamaLLM(
            model_name=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
        )

        response = llm.invoke("Hello")

        mock_client.invoke.assert_called_once_with("Hello")
        assert response is expected_response

    @patch("packages.llm.remote_ollama_llm.ChatOpenAI")
    def test_bind_tools(self, mock_chat_openai):
        tools = [MagicMock(), MagicMock()]
        bound_client = MagicMock()

        mock_client = mock_chat_openai.return_value
        mock_client.bind_tools.return_value = bound_client

        llm = RemoteOllamaLLM(
            model_name=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
        )

        result = llm.bind_tools(tools)

        mock_client.bind_tools.assert_called_once_with(tools)
        assert result is bound_client

    @patch("packages.llm.remote_ollama_llm.ChatOpenAI")
    def test_client_is_initialized_only_once(self, mock_chat_openai):
        llm = RemoteOllamaLLM(
            model_name=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
        )

        llm.invoke("First message")
        llm.invoke("Second message")
        llm.bind_tools([])

        mock_chat_openai.assert_called_once()

    @patch("packages.llm.remote_ollama_llm.ChatOpenAI")
    def test_bind_tools_before_invoke(self, mock_chat_openai):
        llm = RemoteOllamaLLM(
            model_name=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
        )

        llm.bind_tools([])

        mock_chat_openai.assert_called_once()
