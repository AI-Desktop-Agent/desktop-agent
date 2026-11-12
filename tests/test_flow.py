
import pytest
from unittest.mock import patch

from packages.llm.llm_manager import LLMManager
from packages.llm.openrouter_llm import OpenRouterLLM
from packages.llm.ollama_llm import OllamaLLM
from packages.llm.hugging_face_llm import HuggingFaceLLM
from packages.llm.remote_ollama_provider import RemoteOllamaLLM


class TestLLMManager:

    def setup_method(self):
        self.manager = LLMManager()

    @pytest.mark.parametrize(
        "provider, expected_class",
        [
            ("openrouter", OpenRouterLLM),
            ("ollama", OllamaLLM),
            ("huggingface", HuggingFaceLLM),
            ("remote_ollama", RemoteOllamaLLM),
        ],
    )
    def test_chat_provider_selection(self, monkeypatch, provider, expected_class):
        monkeypatch.setenv("LLM_PROVIDER", provider)
        monkeypatch.setenv("HF_MODEL", "test-model")
        monkeypatch.setenv("HF_API_KEY", "test-key")

        llm = self.manager.get_chat_llm()

        assert isinstance(llm, expected_class)

    def test_default_provider_is_openrouter(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)

        llm = self.manager.get_chat_llm()

        assert isinstance(llm, OpenRouterLLM)

    def test_provider_selection_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "REMOTE_OLLAMA")

        llm = self.manager.get_chat_llm()

        assert isinstance(llm, RemoteOllamaLLM)

    def test_unknown_provider_raises_error(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "invalid_provider")

        with pytest.raises(ValueError, match="Unknown LLM provider"):
            self.manager.get_chat_llm()

    def test_chat_llm_is_initialized_lazily(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "remote_ollama")

        assert self.manager.chat_llm is None

        llm = self.manager.get_chat_llm()

        assert llm is not None
        assert self.manager.chat_llm is llm

    def test_chat_llm_is_cached(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "remote_ollama")

        first = self.manager.get_chat_llm()
        second = self.manager.get_chat_llm()

        assert first is second

    def test_embedding_provider_is_not_configured(self):
        with pytest.raises(
            NotImplementedError,
            match="embedding provider is not configured",
        ):
            self.manager.get_embedding_llm()

    def test_structured_provider_is_not_configured(self):
        with pytest.raises(
            NotImplementedError,
            match="structured provider is not configured",
        ):
            self.manager.get_structured_llm()
