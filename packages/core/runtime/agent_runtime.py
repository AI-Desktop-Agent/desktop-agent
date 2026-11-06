
import asyncio

from packages.audio.recording.microphone_recorder import MicrophoneRecorder
from packages.core.interfaces.speech_to_text_provider import SpeechToTextProvider
from packages.core.interfaces.text_to_speech_provider import TextToSpeechProvider


class AgentRuntime:

    def __init__(
        self,
        graph,
        stt: SpeechToTextProvider,
        recorder: MicrophoneRecorder,
        tts: TextToSpeechProvider
    ):
        self.graph = graph
        self.stt = stt
        self.recorder = recorder
        self.tts = tts

    def run(self):
        print("[Agent] Started. Press Ctrl+C to stop.")

        try:
            asyncio.run(self._run_async())

        except KeyboardInterrupt:
            print("\n[Agent] Stopping...")

        finally:
            self._destroy()

    async def _run_async(self):
        while True:
            try:
                print("\n[Agent] Listening...")

                audio = self._record_audio()
                text = self._transcribe_audio(audio)

                if not text or not text.strip():
                    print("[Agent] No speech recognized.")
                    continue

                print(f"[User]: {text}")

                response = await self._process_text_async(text)

                print(f"[Agent]: {response}")

                if response and response.strip():
                    self.tts.speak(response)

            except Exception as exc:
                print(f"[Agent] Request failed: {exc}")

    async def _process_text_async(self, text: str) -> str:
        result = await self.graph.ainvoke({
            "messages": [
                {"role": "user", "content": text}
            ]
        })

        return result["messages"][-1].content

    def _record_audio(self):
        return self.recorder.record()

    def _transcribe_audio(self, audio):
        return self.stt.transcribe(audio)

    def _destroy(self):
        for component in (self.stt, self.tts):
            try:
                component.destroy()
            except Exception as exc:
                print(
                    f"[Agent] Cleanup failed for "
                    f"{type(component).__name__}: {exc}"
                )

        print("[Agent] Resources released.")
