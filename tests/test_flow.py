
import os
import sys
import traceback

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool

from packages.llm.openrouter_llm import OpenRouterLLM
from dotenv import load_dotenv

load_dotenv()

def run_test(name, test_function):
    print(f"\n{'=' * 55}")
    print(f"TEST: {name}")
    print("=" * 55)

    try:
        test_function()
        print(f"[PASS] {name}")
        return True

    except Exception as exc:
        print(f"[FAIL] {name}")
        print(f"Reason: {exc}")
        traceback.print_exc()
        return False


# --------------------------------------------------
# TEST 1: OpenRouter API connectivity
# --------------------------------------------------

def test_openrouter_connection():
    llm = OpenRouterLLM()

    response = llm.invoke([
        HumanMessage(content="Reply with exactly: OpenRouter working")
    ])

    assert isinstance(response, AIMessage)
    assert response.content

    print("Response:", response.content)


# --------------------------------------------------
# TEST 2: OpenRouter tool binding
# --------------------------------------------------

@tool
def test_calculator(value: int) -> int:
    """Return the square of an integer."""
    return value * value


def test_openrouter_tool_binding():
    llm = OpenRouterLLM()

    llm_with_tools = llm.bind_tools([test_calculator])

    assert llm_with_tools is not None

    print("Tool binding successful.")


# --------------------------------------------------
# TEST 3: Actual OpenRouter tool calling
# --------------------------------------------------

def test_openrouter_tool_call():
    llm = OpenRouterLLM()

    llm_with_tools = llm.bind_tools([test_calculator])

    response = llm_with_tools.invoke([
        HumanMessage(
            content=(
                "You must use the test_calculator tool "
                "with value 7. Do not calculate it yourself."
            )
        )
    ])

    print("Response:", response)

    assert isinstance(response, AIMessage)
    assert response.tool_calls, "Model did not call the tool."

    tool_call = response.tool_calls[0]

    assert tool_call["name"] == "test_calculator"
    assert tool_call["args"]["value"] == 7

    print("Tool call:", tool_call)


# --------------------------------------------------
# TEST 4: LangGraph
# --------------------------------------------------

def test_langgraph():
    from packages.agent_graph.builder import agent_graph

    result = agent_graph.invoke({
        "messages": [
            HumanMessage(content="Say hello in one short sentence.")
        ]
    })

    assert result["messages"]
    assert isinstance(result["messages"][-1], AIMessage)

    print("Agent response:", result["messages"][-1].content)


# --------------------------------------------------
# TEST 5: Speech-to-text
# --------------------------------------------------

def test_stt():
    from packages.speech.faster_whisper_stt import FasterWhisperSTT
    from packages.audio.recording.microphone_recorder import MicrophoneRecorder

    recorder = MicrophoneRecorder()
    stt = FasterWhisperSTT()

    try:
        print("Speak a short sentence...")
        audio = recorder.record()

        text = stt.transcribe(audio)

        assert text and text.strip()

        print("Transcription:", text)

    finally:
        stt.destroy()


# --------------------------------------------------
# TEST 6: Text-to-speech
# --------------------------------------------------

def test_tts():
    from packages.speech.tts.pyttsx3_tts import Pyttsx3TTS

    tts = Pyttsx3TTS(rate=175, volume=1.0)

    try:
        tts.speak("Text to speech is working correctly.")
    finally:
        tts.destroy()


# --------------------------------------------------
# TEST 7: Complete voice pipeline
# --------------------------------------------------

def test_voice_pipeline():
    from packages.agent_graph.builder import agent_graph
    from packages.speech.faster_whisper_stt import FasterWhisperSTT
    from packages.audio.recording.microphone_recorder import MicrophoneRecorder
    from packages.speech.tts.pyttsx3_tts import Pyttsx3TTS

    recorder = MicrophoneRecorder()
    stt = FasterWhisperSTT()
    tts = Pyttsx3TTS(rate=175, volume=1.0)

    try:
        print("Speak a question...")
        audio = recorder.record()

        text = stt.transcribe(audio)
        assert text and text.strip()

        print("You said:", text)

        result = agent_graph.invoke({
            "messages": [HumanMessage(content=text)]
        })

        response = result["messages"][-1].content

        assert response and response.strip()

        print("Agent:", response)
        tts.speak(response)

    finally:
        stt.destroy()
        tts.destroy()


# --------------------------------------------------
# TEST 8: Continuous voice agent
# --------------------------------------------------

def test_continuous_agent():
    from packages.agent_graph.builder import agent_graph
    from packages.core.runtime.agent_runtime import AgentRuntime
    from packages.speech.faster_whisper_stt import FasterWhisperSTT
    from packages.audio.recording.microphone_recorder import MicrophoneRecorder
    from packages.speech.tts.pyttsx3_tts import Pyttsx3TTS

    runtime = AgentRuntime(
        graph=agent_graph,
        stt=FasterWhisperSTT(),
        recorder=MicrophoneRecorder(),
        tts=Pyttsx3TTS(rate=175, volume=1.0)
    )

    runtime.run()


# --------------------------------------------------
# TEST RUNNER
# --------------------------------------------------

TESTS = [
    ("OpenRouter connection", test_openrouter_connection),
    ("OpenRouter tool binding", test_openrouter_tool_binding),
    ("OpenRouter tool calling", test_openrouter_tool_call),
    ("LangGraph", test_langgraph),
    ("Speech-to-text", test_stt),
    ("Text-to-speech", test_tts),
    ("Complete voice pipeline", test_voice_pipeline),
    ("Continuous voice agent", test_continuous_agent),
]


def main():
    if not os.getenv("OPENROUTER_API_KEY"):
        print("[ERROR] OPENROUTER_API_KEY is missing.")
        return

    for name, test_function in TESTS:
        passed = run_test(name, test_function)

        if not passed:
            print("\nTesting stopped because a test failed.")
            return

        # Continuous agent is intentionally the final test.
        if name == "Continuous voice agent":
            print("\nPress Ctrl+C to stop the agent.")


if __name__ == "__main__":
    main()
