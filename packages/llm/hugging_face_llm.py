from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from packages.llm.llm_provider import LLMProvider

class HuggingFaceLLM(LLMProvider):
    def __init__(self, model_name: str, api_key: str, task: str = "text-generation"):
        self.model_name = model_name
        self.api_key = api_key
        self.task = task
        self.client = None
        
    def initialize_client(self):
        llm = HuggingFaceEndpoint(
            repo_id=self.model_name,
            huggingfacehub_api_token=self.api_key,
            task=self.task
        )
        
        self.client = ChatHuggingFace(llm=llm)
        
    def invoke(self, prompt: str) -> str:
        if self.client is None:
            self.initialize_client()
        response = self.client.invoke(prompt)  
        return response