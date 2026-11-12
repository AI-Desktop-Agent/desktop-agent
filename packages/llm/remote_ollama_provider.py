
import os

from langchain_openai import ChatOpenAI
from packages.llm.llm_provider import LLMProvider


class RemoteOllamaLLM(LLMProvider):

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ):
        self.model_name = model_name or os.getenv("REMOTE_OLLAMA_MODEL")
        self.base_url = base_url or os.getenv("REMOTE_OLLAMA_BASE_URL")
        self.api_key = api_key or os.getenv("REMOTE_OLLAMA_API_KEY")
        self.client = None

    def initialize_client(self):
        if not self.model_name:
            raise ValueError("REMOTE_OLLAMA_MODEL is not configured")

        if not self.base_url:
            raise ValueError("REMOTE_OLLAMA_BASE_URL is not configured")

        if not self.api_key:
            raise ValueError("REMOTE_OLLAMA_API_KEY is not configured")

        self.client = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=0.2,
            max_retries=2,
        )

    def invoke(self, prompt):
        if self.client is None:
            self.initialize_client()

        return self.client.invoke(prompt)

    def bind_tools(self, tools):
        if self.client is None:
            self.initialize_client()

        return self.client.bind_tools(tools)
