from packages.audio.recording.microphone_recorder import MicrophoneRecorder
from packages.speech.faster_whisper_stt import FasterWhisperSTT


def main():
    recorder = MicrophoneRecorder(
        silence_duration=1.5,
        max_duration=15,
    )

    stt = FasterWhisperSTT(
        model_size="base.en",
        device="cpu",
        compute_type="int8",
    )

    print("[Pipeline] Initializing STT...")
    stt.initialize()

    audio = recorder.record()

    print("[Pipeline] Transcribing...")

    text = stt.transcribe(audio)

    print(f"[Pipeline] User said: {text}")

    stt.destroy()


if __name__ == "__main__":
    main()