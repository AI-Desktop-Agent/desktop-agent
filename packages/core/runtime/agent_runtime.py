
import asyncio
import uuid
from collections.abc import Mapping, Sequence

from langchain_core.messages import HumanMessage, RemoveMessage
from langgraph.types import Command

from packages.audio.recording.microphone_recorder import MicrophoneRecorder
from packages.core.interfaces.human_interaction import HumanInteraction
from packages.core.runtime.console_human_interaction import (
    ConsoleHumanInteraction,
)
from packages.core.interfaces.speech_to_text_provider import SpeechToTextProvider
from packages.core.interfaces.text_to_speech_provider import TextToSpeechProvider


class AgentRuntime:
    MAX_HISTORY_TURNS = 20

    def __init__(
        self,
        graph,
        stt: SpeechToTextProvider,
        recorder: MicrophoneRecorder,
        tts: TextToSpeechProvider,
        human_interaction: HumanInteraction | None = None,
    ):
        self.graph = graph
        self.stt = stt
        self.recorder = recorder
        self.tts = tts
        self.human_interaction = (
            human_interaction
            if human_interaction is not None
            else ConsoleHumanInteraction()
        )
        self._thread_id = str(uuid.uuid4())

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
        config = {
            "configurable": {
                "thread_id": self._thread_id,
                "user_id": "local-user",
            }
        }
        snapshot = await self.graph.aget_state(config)
        messages = snapshot.values.get("messages", [])

        human_message_indices = [
            index
            for index, message in enumerate(messages)
            if isinstance(message, HumanMessage)
        ]
        updates = []
        if len(human_message_indices) >= self.MAX_HISTORY_TURNS:
            first_retained_message = human_message_indices[
                -(self.MAX_HISTORY_TURNS - 1)
            ]
            updates.extend(
                RemoveMessage(id=message.id)
                for message in messages[:first_retained_message]
                if message.id is not None
            )

        updates.append(HumanMessage(content=text))
        result = await self.graph.ainvoke(
            {"messages": updates},
            config=config,
        )

        while result.get("__interrupt__"):
            interruptions = result["__interrupt__"]
            if len(interruptions) != 1:
                raise RuntimeError(
                    "The agent runtime supports one human interaction at a time."
                )

            resume_value = await self._resolve_human_interaction(
                interruptions[0].value
            )
            result = await self.graph.ainvoke(
                Command(resume=resume_value),
                config=config,
            )

        return result["messages"][-1].content

    async def _resolve_human_interaction(self, request: object) -> str | bool:
        if not isinstance(request, Mapping):
            raise TypeError("Graph interrupt payload must be a mapping.")

        kind = request.get("kind")
        prompt = request.get("prompt")
        options = request.get("options", [])

        if kind not in {"clarification", "approval"}:
            raise ValueError("Graph interrupt has an unsupported interaction kind.")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Graph interrupt must include a prompt.")
        if (
            not isinstance(options, Sequence)
            or isinstance(options, (str, bytes))
            or any(not isinstance(option, str) for option in options)
        ):
            raise ValueError("Graph interrupt options must be a list of strings.")

        answer = await self.human_interaction.ask_clarification(
            prompt,
            options,
        )

        if kind == "approval":
            return answer.strip().casefold() == "approve"

        return answer

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
