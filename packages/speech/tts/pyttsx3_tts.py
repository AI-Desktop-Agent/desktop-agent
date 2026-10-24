from typing import Optional

import pyttsx3

from packages.core.interfaces.text_to_speech_provider import TextToSpeechProvider

class Pyttsx3TTS(TextToSpeechProvider):
    """Offline TTS provider using installed system voices."""
    
    def __init__(
        self,
        rate: int = 175,
        volume: float = 1.0,
        voice_id: Optional[str] = None
    ):
        if rate <= 0:
            raise ValueError("rate must be positive")
        
        if not 0.0 <= volume <= 1.0:
            raise ValueError("volume must be between 0.0 and 1.0")
        
        self.rate=rate
        self.volume=volume
        self.voice_id=voice_id
        self.engine=None
        
    def initialize(self) -> None:
        if self.engine is not None:
            return
        
        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        engine.setProperty("volume", self.volume)
        
        if self.voice_id is not None:
            available_ids = { voice.id for voice in engine.getProperty("voices")}
            
            if self.voice_id not in available_ids:
                engine.stop()
                raise ValueError(f"Voice ID not found: {self.voice_id}")
            engine.setProperty("voice", self.voice_id)
        
        self.engine = engine
        
    def speak(self, text: str) -> None:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        
        text = text.strip()
        if not text:
            return
        
        self.initialize()
        
        self.engine.say(text)
        self.runAndWait()
        
    def destroy(self) -> None:
        if self.engine is not None:
            self.engine.stop()
            self.engine = None
         