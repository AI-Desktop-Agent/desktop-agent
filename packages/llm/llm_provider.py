from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def invoke(self, prompt: str) -> str:
        """Invoke the LLM provider with the given prompt and return the response."""
        pass