from packages.audio.recording.microphone_recorder import MicrophoneRecorder


def main():
    recorder = MicrophoneRecorder(
        silence_duration=1.5,
        max_duration=15,
    )

    audio = recorder.record()

    print(
        f"[Test] Recorded {len(audio.getvalue())} bytes of audio."
    )


if __name__ == "__main__":
    main()