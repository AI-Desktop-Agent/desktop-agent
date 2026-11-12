
import os

from packages.llm.openrouter_llm import OpenRouterLLM
from packages.llm.ollama_llm import OllamaLLM
from packages.llm.hugging_face_llm import HuggingFaceLLM
from .remote_ollama_provider import RemoteOllamaLLM


class LLMManager:

    def __init__(self):
        self.chat_llm = None
        self.embedding_llm = None
        self.structured_llm = None

    def __set_llm(self, model_type):
        provider = os.getenv("LLM_PROVIDER", "openrouter").lower()

        if model_type == "chat":
            if provider == "openrouter":
                self.chat_llm = OpenRouterLLM(
                    model_name=os.getenv("OPENROUTER_MODEL", "openrouter/free")
                )

            elif provider == "ollama":
                self.chat_llm = OllamaLLM(
                    model_name=os.getenv("OLLAMA_MODEL", "llama3.2")
                )

            elif provider == "huggingface":
                self.chat_llm = HuggingFaceLLM(
                    model_name=os.getenv("HF_MODEL"),
                    api_key=os.getenv("HF_API_KEY")
                )

            elif provider == "remote_ollama":
                self.chat_llm = RemoteOllamaLLM()

            else:
                raise ValueError(f"Unknown LLM provider: {provider}")

        elif model_type in ("embedding", "structured"):
            raise NotImplementedError(
                f"{model_type} provider is not configured yet."
            )

    def get_chat_llm(self):
        if self.chat_llm is None:
            self.__set_llm("chat")

        return self.chat_llm

    def get_embedding_llm(self):
        if self.embedding_llm is None:
            self.__set_llm("embedding")

        return self.embedding_llm

    def get_structured_llm(self):
        if self.structured_llm is None:
            self.__set_llm("structured")

        return self.structured_llm


llm_manager = LLMManager()
