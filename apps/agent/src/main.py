from collections.abc import Mapping

from dotenv import load_dotenv
from langgraph.types import interrupt

from packages.tools.command_line.executor import CommandExecutor
from packages.core.runtime.console_human_interaction import (
    ConsoleHumanInteraction,
)
from packages.security.gateway import gateway

load_dotenv()
CommandExecutor.configure([
    r"C:\Users\Manpreet Singh\OneDrive\Desktop\desktop agent test dir"
])

human_interaction = ConsoleHumanInteraction()


def request_graph_approval(
    tool_name: str,
    risk: str,
    args: Mapping[str, object],
    principal: str,
) -> bool:
    prompt = "\n".join(
        (
            "Approve this tool action?",
            f"Tool: {human_interaction._safe_terminal_text(tool_name, 200)}",
            f"Risk: {human_interaction._safe_terminal_text(risk, 50)}",
            f"User: {human_interaction._safe_terminal_text(principal, 200)}",
            f"Arguments: {human_interaction._format_arguments(args)}",
        )
    )
    return interrupt(
        {
            "kind": "approval",
            "prompt": prompt,
            "options": ["approve", "deny"],
        }
    )


gateway.set_approval_callback(request_graph_approval)

from packages.core.runtime.agent_runtime import AgentRuntime
from packages.agent_graph.builder import agent_graph
from packages.speech.faster_whisper_stt import FasterWhisperSTT
from packages.audio.recording.microphone_recorder import MicrophoneRecorder
from packages.speech.tts.pyttsx3_tts import Pyttsx3TTS

def main():
    stt = FasterWhisperSTT()
    tts = Pyttsx3TTS(rate=175, volume=1.0)
    recorder = MicrophoneRecorder()
    
    obj = AgentRuntime(
        graph=agent_graph,
        stt=stt,
        recorder=recorder,
        tts=tts
    )
    obj.run()

if __name__ == "__main__":
    main()
