import io
import queue
import wave

import numpy as np
import sounddevice as sd

class MicrophoneRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, silence_threshold: float = 0.01, silence_duration: float = 1.5, max_duration: float = 15.0):
        self.sample_rate = sample_rate
        self.channels = channels
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration
        self.max_duration = max_duration

        self.audio_queue = queue.Queue()
        self.recording = False
        
    def record(self) -> io.BytesIO:
        audio_queue = queue.Queue()
        
        def callback(indata, frames, time, status):
            if status:
                print(f"[Recorder] {status}")
            audio_queue.put(indata.copy())
        
        print("[Recorder] Listening...")
        
        frames = []
        speech_started = False
        silent_samples = 0
        
        silence_limit = int(self.silence_duration * self.sample_rate)
        
        max_samples = int(self.max_duration * self.sample_rate)

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            callback=callback,
        ):
            while sum(len(chunk) for chunk in frames) < max_samples:
                try:
                    chunk = audio_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                frames.append(chunk)
                
                volume = np.sqrt(np.mean(chunk**2))
                
                if volume > self.silence_threshold:
                    speech_started = True
                    silent_samples = 0
                elif speech_started:
                    silent_samples += len(chunk)
                    
                    if silent_samples >= silence_limit:
                        break
                
        print("[Recorder] Recording stopped.")
        audio= np.concatenate(frames, axis=0)
        audio_int16 = (audio * 32767).astype(np.int16)
        buffer = io.BytesIO()
        
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(audio_int16.tobytes())
        buffer.seek(0)
        return buffer