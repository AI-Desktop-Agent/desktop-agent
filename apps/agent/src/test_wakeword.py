from packages.audio.wakeword.openwakeword_detector import (
    OpenWakeWordDetector,
)


def wake_word_detected(word: str):
    print()
    print("==============================")
    print(f"WAKE WORD DETECTED: {word}")
    print("==============================")
    print()


def main():

    detector = OpenWakeWordDetector(
        wake_word="hey_jarvis",
        threshold=0.5,
    )

    detector.on_detected(wake_word_detected)

    try:

        detector.initialize()
        detector.start()

        print("Agent is listening...")
        print("Press Ctrl+C to stop.")

        while True:
            pass

    except KeyboardInterrupt:

        print("\nStopping...")

    finally:

        detector.destroy()


if __name__ == "__main__":
    main()