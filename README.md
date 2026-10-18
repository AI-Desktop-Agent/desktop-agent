
# Desktop Agent

A modular and extensible desktop AI agent designed to support voice interaction, local speech recognition, LLM providers, tools, memory, and desktop automation.

## Architecture

The project is designed around a modular agent runtime with replaceable components:

- Audio recording
- Wake-word detection
- Speech-to-text (STT)
- LLM providers
- Text-to-speech (TTS)
- Tools
- Memory
- Security
- Desktop UI

## Current Status

### Audio Recording and Offline Speech Recognition

- [x] Microphone input using `sounddevice`
- [x] Audio recording at 16 kHz, mono
- [x] Basic silence detection using an RMS volume threshold
- [x] Maximum recording duration
- [x] Local speech recognition using Faster-Whisper
- [x] Configurable Whisper model, device, compute type, and beam size
- [x] Optional initial prompt for technical vocabulary
- [x] Repeated listen-and-transcribe loop without requiring a wake word
- [x] STT model cleanup when the listening loop exits

### Wake-Word Detection

- [x] Wake-word detection implementation
- [x] Detection callback
- [ ] Integration with the active agent runtime

Wake-word detection remains available in the project but is not required by the current listening and transcription entry point.

### Planned Components

- [ ] Event bus
- [ ] Agent runtime integration
- [ ] Agent state management
- [ ] LLM integration
- [ ] Text-to-speech
- [ ] Tool system
- [ ] Memory
- [ ] Security integration
- [ ] Desktop UI

## Speech Recognition

The current offline transcription implementation uses Faster-Whisper.

Default configuration:

- Model: `base.en`
- Device: CPU
- Compute type: `int8`
- Beam size: `5`
- Sample rate: `16000 Hz`
- Channels: `1`

The microphone recorder collects audio until the configured silence duration is reached or the maximum recording duration is reached. Faster-Whisper transcribes the completed recording locally.

The recorder uses a basic RMS threshold for silence detection; it is not a dedicated neural voice activity detection system.

## Run the Listening Pipeline

Activate your virtual environment, install the project's requirements, and run the test entry point from the repository root:

```powershell
python -m tests.test_listen_to_stt
```

Speak after the agent starts listening. The recognized text is printed in the terminal. Press `Ctrl+C` to stop.

The first transcription may take longer while the Whisper model loads.

## Dependencies

The current audio and speech-recognition dependencies include:

- `sounddevice` — microphone input
- `numpy` — audio array processing
- `faster-whisper` — local speech recognition
- `av` — audio/video dependency used by Faster-Whisper
- `openwakeword` — wake-word detection

## Future Improvements

- Connect transcribed user requests to an LLM provider.
- Add a proper voice activity detection component.
- Improve transcription accuracy for technical terms and application commands.
- Integrate text-to-speech.
- Connect the agent runtime, tools, memory, and desktop UI.
- Evaluate optional streaming STT providers while retaining the offline fallback.
