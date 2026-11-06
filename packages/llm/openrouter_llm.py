import os

from langchain_openai import ChatOpenAI
from packages.llm.llm_provider import LLMProvider


class OpenRouterLLM(LLMProvider):

    def __init__(self, model_name: str = "openrouter/free"):
        self.model_name = model_name
        self.client = None

    def initialize_client(self):
        api_key = os.getenv("OPENROUTER_API_KEY")

        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured")

        self.client = ChatOpenAI(
            model=self.model_name,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
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