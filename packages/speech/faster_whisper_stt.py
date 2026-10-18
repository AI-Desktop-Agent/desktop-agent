
from typing import BinaryIO, Optional

from faster_whisper import WhisperModel
from packages.core.interfaces.speech_to_text_provider import SpeechToTextProvider


class FasterWhisperSTT(SpeechToTextProvider):
    def __init__(
        self,
        model_size: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        beam_size: int = 5,
        initial_prompt: Optional[str] = None,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.initial_prompt = initial_prompt
        self.model = None

    def initialize(self):
        print("[STT] Loading Whisper model...")
        self.model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        print("[STT] Whisper model loaded successfully.")

    def transcribe(self, audio: BinaryIO) -> str:
        if self.model is None:
            self.initialize()

        audio.seek(0)

        options = {"beam_size": self.beam_size}
        if self.initial_prompt:
            options["initial_prompt"] = self.initial_prompt

        segments, _ = self.model.transcribe(audio, **options)
        return " ".join(segment.text.strip() for segment in segments).strip()

    def destroy(self) -> None:
        self.model = None
        print("[STT] Whisper model destroyed.")
