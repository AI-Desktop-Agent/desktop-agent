
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
        chat_provider = os.getenv("CHAT_LLM_PROVIDER", "openrouter").lower()
        embedd_provider = os.getenv("EMBEDD_LLM_PROVIDER", "openrouter").lower()
        struct_provider = os.getenv("STRUCT_LLM_PROVIDER", "openrouter").lower()

        if model_type == "chat":
            if chat_provider == "openrouter":
                self.chat_llm = OpenRouterLLM(
                    model_name=os.getenv("OPENROUTER_CHAT_MODEL", "openrouter/free")
                )

            elif chat_provider == "ollama":
                self.chat_llm = OllamaLLM(
                    model_name=os.getenv("OLLAMA_CHAT_MODEL", "llama3.2")
                )

            elif chat_provider == "huggingface":
                self.chat_llm = HuggingFaceLLM(
                    model_name=os.getenv("HF_MODEL"),
                    api_key=os.getenv("HF_API_KEY")
                )

            elif chat_provider == "remote_ollama":
                self.chat_llm = RemoteOllamaLLM()

            else:
                raise ValueError(f"Unknown LLM provider: {chat_provider}")

        elif model_type == 'embedding':
            if embedd_provider == "openrouter":
                self.chat_llm = OpenRouterLLM(
                    model_name=os.getenv("OPENROUTER_EMBEDD_MODEL", "openrouter/free")
                )

            elif embedd_provider == "ollama":
                self.chat_llm = OllamaLLM(
                    model_name=os.getenv("OLLAMA_EMBEDD_MODEL", "llama3.2")
                )

            elif embedd_provider == "huggingface":
                self.chat_llm = HuggingFaceLLM(
                    model_name=os.getenv("HF_MODEL"),
                    api_key=os.getenv("HF_API_KEY")
                )

            elif embedd_provider == "remote_ollama":
                self.chat_llm = RemoteOllamaLLM()

            else:
                raise ValueError(f"Unknown LLM provider: {embedd_provider}")
            
        else:
            if struct_provider == "openrouter":
                self.chat_llm = OpenRouterLLM(
                    model_name=os.getenv("OPENROUTER_STRUCT_MODEL", "openrouter/free")
                )

            elif struct_provider == "ollama":
                self.chat_llm = OllamaLLM(
                    model_name=os.getenv("OLLAMA_STRUCT_MODEL", "llama3.2")
                )

            elif struct_provider == "huggingface":
                self.chat_llm = HuggingFaceLLM(
                    model_name=os.getenv("HF_MODEL"),
                    api_key=os.getenv("HF_API_KEY")
                )

            elif struct_provider == "remote_ollama":
                self.chat_llm = RemoteOllamaLLM()

            else:
                raise ValueError(f"Unknown LLM provider: {struct_provider}")

            

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
