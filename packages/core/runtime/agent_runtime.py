import time
from packages.audio.recording.microphone_recorder import MicrophoneRecorder
from packages.core.interfaces.speech_to_text_provider import SpeechToTextProvider
from packages.core.interfaces.text_to_speech_provider import TextToSpeechProvider


class AgentRuntime:
    def __init__(self, graph, stt: SpeechToTextProvider, recorder: MicrophoneRecorder, tts: TextToSpeechProvider):
        self.graph = graph
        self.stt = stt
        self.recorder = recorder
        self.tts = tts
        
    def run(self):
        try:
            while True:
                print("\n[Agent] Listening... Speak now.")
                audio = self._record_audio()
    
                print("[Agent] Transcribing...")
                text = self._transcribe_audio(audio)
    
                if text:
                    response = self._process_text(text)
                    print(f"[Agent]: {response}")
                    try:
                        self.tts.speak(response)
                    except Exception as exc:
                        print(f"[TTS] Speech output failed: {exc}")
                else:
                    print("[Agent] No speech recognized.")
    
                time.sleep(0.3)
        except KeyboardInterrupt:
            print("\nAgent Stopped")
            
        finally:
            self._destroy()
    
    def _process_text(self, text):
        # Process the text and update the state graph accordingly
        result = self.graph.invoke({
            "messages": [
                {"role": "user", "content": text}
            ]
        })
        return result["messages"][-1].content
    
    def _record_audio(self):
        # Record audio using the recorder and return the audio data
        audio = self.recorder.record()
        
        return audio
    
    def _transcribe_audio(self, audio):
        # Transcribe the audio using the STT model and return the text
        return self.stt.transcribe(audio)
        
    def _destroy(self):
        for component in (self.stt, self.tts):
            try:
                component.destroy()
            except Exception as exc:
                print(
                    f"[Agent] Cleanup failed for"
                    f"{type(component).__name__}: {exc}"
                )
        print("[Agent] Resources released.")