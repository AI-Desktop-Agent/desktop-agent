from langchain_ollama import ChatOllama
from packages.llm.llm_provider import LLMProvider

class OllamaLLM(LLMProvider):
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.client = None
        
    def initialize_client(self):
        self.client = ChatOllama(model=self.model_name)
    
    def invoke(self, prompt: str) -> str:
        if self.client is None:
            self.initialize_client()
        response = self.client.invoke(prompt)  
        return response
