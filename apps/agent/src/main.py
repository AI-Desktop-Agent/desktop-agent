
import time

from packages.audio.recording.microphone_recorder import MicrophoneRecorder
from packages.speech.faster_whisper_stt import FasterWhisperSTT


def main():
    recorder = MicrophoneRecorder(
        sample_rate=16000,
        channels=1,
        silence_threshold=0.01,
        silence_duration=1.5,
        max_duration=15.0,
    )

    stt = FasterWhisperSTT(
        model_size="base.en",
        device="cpu",
        compute_type="int8",
        beam_size=5,
        initial_prompt=(
            "Desktop Agent, Chrome, Python, Faster-Whisper, "
            "speech recognition, openbrowser, search."
        ),
    )

    print("[Agent] Initializing speech recognition...")
    stt.initialize()
    print("[Agent] Ready.")

    try:
        while True:
            print("\n[Agent] Listening... Speak now.")
            audio = recorder.record()

            print("[Agent] Transcribing...")
            text = stt.transcribe(audio)

            if text:
                print(f"\n[You]: {text}")
            else:
                print("[Agent] No speech recognized.")

            time.sleep(0.3)

    except KeyboardInterrupt:
        print("\n[Agent] Stopped.")

    finally:
        stt.destroy()


if __name__ == "__main__":
    main()
