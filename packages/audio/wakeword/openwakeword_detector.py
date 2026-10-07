import queue
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

from packages.core.interfaces.wake_word_provider import WakeWordProvider


class OpenWakeWordDetector(WakeWordProvider):

    def __init__(
        self,
        wake_word: str = "hey_jarvis",
        threshold: float = 0.5,
        sample_rate: int = 16000,
    ):
        self.wake_word = wake_word
        self.threshold = threshold
        self.sample_rate = sample_rate

        self.model: Optional[Model] = None

        self.audio_queue = queue.Queue()
        self.running = False
        self.thread: Optional[threading.Thread] = None

        self.callback: Optional[Callable[[str], None]] = None

    def initialize(self) -> None:
        """
        Load the wake-word model.
        """

        print("[WakeWord] Loading model...")

        self.model = Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx"
        )

        print("[WakeWord] Model loaded.")

    def on_detected(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback that will be called
        whenever the wake word is detected.
        """

        self.callback = callback

    def _audio_callback(self, indata, frames, time, status):
        """
        Called continuously by the microphone stream.
        """

        if status:
            print(f"[Audio] {status}")

        audio = indata[:, 0].copy()

        self.audio_queue.put(audio)

    def _process_audio(self) -> None:
        """
        Continuously process microphone audio.
        """

        while self.running:

            try:
                audio = self.audio_queue.get(timeout=1)
            except queue.Empty:
                continue

            if self.model is None:
                continue

            # Convert microphone audio to int16.
            audio_int16 = (audio * 32767).astype(np.int16)

            prediction = self.model.predict(audio_int16)

            score = prediction.get(self.wake_word, 0)

            if score >= self.threshold:

                print(
                    f"[WakeWord] Detected: "
                    f"{self.wake_word} "
                    f"(score={score:.2f})"
                )

                if self.callback:
                    self.callback(self.wake_word)

    def start(self) -> None:
        """
        Start microphone capture and wake-word detection.
        """

        if self.running:
            return

        if self.model is None:
            self.initialize()

        self.running = True

        self.thread = threading.Thread(
            target=self._process_audio,
            daemon=True,
        )

        self.thread.start()

        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=1280,
            callback=self._audio_callback,
        )

        self.stream.start()

        print("[WakeWord] Listening...")

    def stop(self) -> None:
        """
        Stop microphone capture.
        """

        if not self.running:
            return

        self.running = False

        if hasattr(self, "stream"):
            self.stream.stop()
            self.stream.close()

        if self.thread:
            self.thread.join(timeout=2)

        print("[WakeWord] Stopped.")

    def destroy(self) -> None:
        """
        Release all resources.
        """

        self.stop()

        self.model = None
        self.callback = None

        print("[WakeWord] Destroyed.")