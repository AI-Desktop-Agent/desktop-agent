from abc import ABC, abstractmethod
from typing import Any, Sequence

class LLMProvider(ABC):
    @abstractmethod
    def invoke(self, prompt: Any):
        """Invoke the LLM provider with the given prompt and return the response."""
        pass
    
    @abstractmethod
    def bind_tools(self, tools: Sequence):
        """Bind tools to the LLM provider."""
        pass