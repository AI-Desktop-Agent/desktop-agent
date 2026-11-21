# Desktop Agent

Desktop Agent is a modular Windows voice assistant built around microphone capture, local speech recognition, an LLM-powered LangGraph workflow, tool execution, text-to-speech, and security controls.

The agent currently listens continuously, transcribes speech locally, sends the request through a LangGraph agent, optionally executes an approved tool, speaks the response, and repeats.

## Current capabilities

- **Voice input**
  - Microphone recording through `sounddevice`
  - Configurable recording duration and silence detection
  - Offline transcription with Faster-Whisper
  - Wake-word provider implementations, including OpenWakeWord

- **Agent workflow**
  - LangGraph graph for response generation and tool routing
  - Async agent runtime
  - Tool-capable LLM responses
  - Voice and text pipeline integration
  - Automatic cleanup of STT and TTS resources

- **LLM providers**
  - OpenRouter
  - Ollama
  - Remote Ollama
  - Hugging Face
  - Separate environment configuration for chat, embedding, and structured providers

- **Tools**
  - Web search
  - Windows command-line interpretation and execution
  - Structured command planning
  - Command validation and command risk classification
  - Tool registration and discovery

- **Text-to-speech**
  - Offline speech output with `pyttsx3`
  - Configurable speech rate, volume, and voice

- **Security**
  - Central tool-security gateway
  - Permission scopes
  - Risk policies and taint-aware authorization
  - Rate limiting
  - Audit logging
  - Approval callbacks
  - Blocked and denied execution paths

- **Desktop voice pipeline**
  - Listen with a microphone
  - Transcribe the request locally
  - Process the request through the LLM graph
  - Execute registered tools when appropriate
  - Speak the resulting response

## Project status

| Area | Status |
| --- | --- |
| Microphone recording | Implemented |
| Offline speech-to-text | Implemented |
| Wake-word detection providers | Implemented; not the default runtime entry point |
| Agent runtime | Implemented |
| LangGraph response/tool graph | Implemented |
| OpenRouter, Ollama, remote Ollama, and Hugging Face providers | Implemented |
| Web-search tool | Implemented |
| Windows command-line tool | Implemented with validation and security |
| Text-to-speech | Implemented |
| Tool security gateway | Implemented |
| Audit, policy, rate-limit, taint, and approval support | Implemented |
| Persistent memory | Planned |
| Desktop UI | Planned |
| Wake-word runtime integration | Planned |
| Event bus | Planned |

The test suite is currently passing. The most complete tested workflows cover graph/tool routing, secure tool execution, audio recording, STT, the voice pipeline, and command/security behavior.

## Architecture

```text
apps/
  agent/src/main.py              Main desktop-agent entry point

packages/
  agent_graph/
    builder.py                   LangGraph construction and routing
    state.py                     Agent state
    nodes/                       LLM response and secure tool nodes
    prompts/                     Agent and command-interpreter prompts

  core/
    interfaces/                  STT, TTS, and wake-word contracts
    runtime/agent_runtime.py     Continuous listen/process/speak loop

  audio/
    recording/                   Microphone and silence handling
    wakeword/                    Wake-word provider implementation

  speech/
    faster_whisper_stt.py        Offline Faster-Whisper STT
    tts/pyttsx3_tts.py           Offline system TTS

  llm/
    llm_manager.py               Provider selection
    openrouter_llm.py
    ollama_llm.py
    remote_ollama_provider.py
    hugging_face_llm.py

  tools/
    registry.py                  Available LangChain tools
    search/                      Web-search tool
    command_line/                Command planning and execution

  security/
    gateway.py                   Authorization and execution gateway
    policy.py                   Risk and permission policies
    registry.py                 Tool registration
    limits.py                    Rate limiting
    audit.py                     Audit logging
    taint.py                     Untrusted-data tracking

tests/                          Unit and integration-style test entry points
```

## Requirements

- Windows
- Python 3.12
- A working microphone
- One configured LLM provider
- Internet access for remote providers or web search
- For Ollama, a running Ollama service and selected model

Install dependencies:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the repository root. Common settings include:

```dotenv
CHAT_LLM_PROVIDER=openrouter
OPENROUTER_CHAT_MODEL=openrouter/free
OPENROUTER_API_KEY=your-key

STRUCT_LLM_PROVIDER=openrouter
OPENROUTER_STRUCT_MODEL=openrouter/free

EMBEDD_LLM_PROVIDER=openrouter
OPENROUTER_EMBEDD_MODEL=openrouter/free
```

Supported chat/structured/embedding provider values are `openrouter`, `ollama`, `remote_ollama`, and `huggingface`.

Provider-specific configuration examples:

```dotenv
# Ollama
CHAT_LLM_PROVIDER=ollama
OLLAMA_CHAT_MODEL=llama3.2

# Remote Ollama
CHAT_LLM_PROVIDER=remote_ollama

# Hugging Face
CHAT_LLM_PROVIDER=huggingface
HF_MODEL=your-model
HF_API_KEY=your-key
```

Do not commit API keys or other credentials.

## Run the desktop-agent pipeline

From the repository root:

```powershell
python apps\agent\src\main.py
```

The application continuously:

1. Records microphone audio until silence or the maximum duration is reached.
2. Transcribes it with Faster-Whisper.
3. Sends the text through the LangGraph agent.
4. Executes a web or command-line tool through the security gateway when needed.
5. Prints and speaks the final response.

Press `Ctrl+C` to stop.

## Run focused pipelines

Voice/STT pipeline:

```powershell
python -m tests.test_voice_pipeline
```

Listening/transcription test:

```powershell
python -m tests.test_listen_to_stt
```

Wake-word test module:

```powershell
python -m apps.agent.src.test_wakeword
```

Wake-word test modules cover both detection and recording behavior; they are independent diagnostics and are not part of the default main runtime loop.

## Run tests

Run the suite from the repository root so the `packages` namespace resolves correctly:

```powershell
python -m pytest -q
```

Run a focused test module:

```powershell
python -m pytest tests/test_security.py -q
python -m pytest tests/test_voice_pipeline.py -q
```

## Default speech configuration

The Faster-Whisper STT configuration is:

- Model: `base.en`
- Device: CPU
- Compute type: `int8`
- Beam size: `5`
- Sample rate: `16000 Hz`
- Channels: `1`

The offline recorder uses RMS-based silence detection. It is not yet a dedicated neural voice-activity-detection system.

## Security behavior

Tools are registered in the tool registry and executed through the security gateway rather than called directly. Authorization considers:

- Registered tool identity
- Permission scopes
- Tool risk level
- Rate limits
- Taint from external or untrusted input
- Optional user approval
- Audit outcome

Tool output is treated as untrusted data. The agent prompt explicitly prevents tool output from overriding security instructions or the user's original request.

## Known limitations

- Conversation state is currently held only in memory; no persistent memory provider is implemented.
- Wake-word detection exists, but it is not integrated into the main runtime loop.
- RMS silence detection can misdetect quiet speech or background noise.
- There is no desktop graphical interface yet.
- Event-bus and agent-state management components are not yet implemented.
- The command-line tool operates on trusted command names and validated plans, but system execution should still be considered privileged and is governed by the security gateway.

## Planned improvements

- Integrate wake-word detection with `AgentRuntime`
- Add persistent conversation memory
- Add an event bus
- Add desktop UI controls
- Add dedicated voice-activity detection
- Add desktop-control and application tools
- Improve streaming STT and TTS behavior
- Add approval prompts and richer audit review
- Expand command allowlists and tool-specific authorization
