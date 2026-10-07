from abc import ABC, abstractmethod
from typing import BinaryIO

class SpeechToTextProvider(ABC):
    @abstractmethod
    def transcribe(self, audio: BinaryIO) -> str:
        """Convert audio data into text."""
        pass