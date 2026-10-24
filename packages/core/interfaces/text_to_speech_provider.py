from abc import ABC, abstractmethod

class TextToSpeechProvider(ABC):
    """Common interface for interchangeable TTS engines."""
    
    @abstractmethod
    def speak(self, text: str) -> None:
        """Convert text to speech and play it"""
        raise NotImplementedError
    
    @abstractmethod
    def destroy(self) -> None:
        """Release provider resources"""
        raise NotImplementedError