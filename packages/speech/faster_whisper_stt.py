from typing import BinaryIO

from faster_whisper import WhisperModel
from packages.core.interfaces.speech_to_text_provider import SpeechToTextProvider

class FasterWhisperSTT(SpeechToTextProvider):
    def __init__(self, model_size: str = "base.en", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None
        
    def initialize(self):
        print("[STT] Loading Whisper model...")
        
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type
        )
        
        print("[STT] Whisper model loaded successfully.")
    
    def transcribe(self, audio: BinaryIO) -> str:
        if self.model is None:
            self.initialize()
            
        segments, _ = self.model.transcribe(
            audio,
            beam_size=5,
        )
        text = " ".join(segment.text.strip() for segment in segments)
        
        return text.strip()
    
    def destroy(self) -> None:
        self.model = None
        print("[STT] Whisper model destroyed.")