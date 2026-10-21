from packages.llm.hugging_face_llm import HuggingFaceLLM

class LLMManager:
    def __init__(self):
        self.chat_llm = None
        self.embedding_llm = None
        self.structured_llm = None
        
    def __set_llm(self, model_type):
        if model_type == "chat":
            self.chat_llm = HuggingFaceLLM(model_name="gpt-4", api_key="your_api_key")
        elif model_type == "embedding":
            self.embedding_llm = HuggingFaceLLM(model_name="bert-base-uncased", api_key="your_api_key")
        elif model_type == "structured":
            self.structured_llm = HuggingFaceLLM(model_name="t5-base", api_key="your_api_key")
        else:
            raise ValueError(f"Unknown model type: {model_type}")
        
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