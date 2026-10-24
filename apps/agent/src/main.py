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
