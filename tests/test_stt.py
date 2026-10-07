import io
import wave

import numpy as np
import sounddevice as sd

from packages.speech.faster_whisper_stt import FasterWhisperSTT


SAMPLE_RATE = 16000
RECORD_SECONDS = 5


def record_audio() -> io.BytesIO:
    print("Speak now...")

    audio = sd.rec(
        int(RECORD_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.int16,
    )

    sd.wait()

    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(audio.tobytes())

    buffer.seek(0)

    return buffer


def main():
    stt = FasterWhisperSTT(
        model_size="base.en",
        device="cpu",
        compute_type="int8",
    )

    print("[Test] Initializing STT...")
    stt.initialize()

    audio = record_audio()

    print("[Test] Transcribing...")

    text = stt.transcribe(audio)

    print(f"[STT] Result: {text}")

    stt.destroy()


if __name__ == "__main__":
    main()