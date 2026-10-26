# LocalVoiceAgent

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)
![Local](https://img.shields.io/badge/AI-100%25%20Local-orange)

A fully local Windows voice assistant built in Python. It connects real-time speech recognition, a local LLM via Ollama, and neural text-to-speech into a single desktop app — with a custom-rendered animated 3D orb interface and a tool-call loop for everyday desktop automation.

No cloud services. No API keys. Everything runs on your own hardware.

---

## Demo

> *Replace this section with a screen recording or GIF showing the orb animation and a live conversation.*

States the orb cycles through: **Sleeping → Listening → Thinking → Speaking**

---

## Features

| Feature | Detail |
|---|---|
| **Speech recognition** | Faster Whisper, runs fully offline |
| **Language model** | Any Ollama model — default `qwen3:14b` |
| **Text to speech** | Kokoro ONNX (primary) or Piper (fallback) |
| **Input modes** | Wake-word · Push-to-talk · Always-listening · CLI |
| **Desktop tools** | Open apps · Search files · Read files · Web search · Run PowerShell |
| **Safety** | Voice confirmation before commands, blocked executable extensions, configurable file roots |
| **Memory** | Bounded conversation history persisted to JSON |
| **Animated UI** | Custom 3D ring renderer written in NumPy + Pillow — no OpenGL |

---

## Architecture

```
Microphone
    │
    ▼
┌──────────┐    audio    ┌──────────────────┐    text     ┌──────────────┐
│  stt.py  │ ──────────► │    main.py        │ ──────────► │   llm.py     │
│  Faster  │             │  Agent loop       │             │  Ollama API  │
│  Whisper │             │  Mode handling    │ ◄────────── │  Tool-call   │
└──────────┘             │  Voice confirm    │   reply     │  loop (×4)   │
                         └────────┬──────────┘             └──────┬───────┘
                                  │                               │
                         ┌────────▼──────────┐         ┌─────────▼──────┐
                         │    gui.py          │         │   tools.py     │
                         │  Tkinter window    │         │  open_app      │
                         │  orb3d.py renderer │         │  search_files  │
                         │  State animation   │         │  read_file     │
                         └────────────────────┘         │  web_search    │
                                                        │  run_command   │
                                  ┌─────────────────────┴────────────────┤
                                  ▼                                       │
                            ┌──────────┐         ┌──────────┐            │
                            │  tts.py  │         │ memory.py│            │
                            │  Kokoro  │         │  JSON    │ ◄──────────┘
                            │  Piper   │         │  history │
                            └──────────┘         └──────────┘
```

**Tool-call loop:** after each user message, `llm.py` runs up to 4 rounds of tool calls before returning a final spoken reply. Tool results are fed back as `role: tool` messages — the model decides whether to call another tool or synthesise an answer.

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 | Windows 11 |
| Python | 3.10 | 3.11+ |
| RAM | 8 GB | 16 GB |
| Storage | 10 GB free | 20 GB free |
| Audio | Microphone + speakers | Headset |
| GPU | CPU-only (slow first response) | NVIDIA GPU for Whisper + Ollama |
| Ollama | Any tool-capable model | `qwen3:14b` (~10 GB VRAM) |

---

## Quick Start

### 1 — Install Ollama and pull a model

Download [Ollama](https://ollama.com/) and pull the default model:

```powershell
ollama pull qwen3:14b
```

Any model with tool-call support works. Lighter options: `llama3.2:3b`, `mistral:7b`.

### 2 — Set up the Python environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### 3 — Download voice models

```powershell
python download_voices.py          # Kokoro only (~340 MB, recommended)
python download_voices.py --all    # Kokoro + Piper fallback voices
```

### 4 — Launch

```powershell
python -m app.main
```

---

## Run Modes

```powershell
python -m app.main --mode wake     # "Hey Jarvis" to start each turn  (default)
python -m app.main --mode ptt      # Hold Ctrl+Space while speaking
python -m app.main --mode always   # Listen continuously
python -m app.main --cli           # Terminal only, no GUI
python -m app.main --reset         # Clear saved conversation history
```

**Wake mode:** say `Hey Jarvis` to activate, then ask anything. Say `standby` to sleep.  
**Push-to-talk:** hold the configured key, speak, release to submit.

---

## Configuration

All settings are in `app/settings.py`:

| Setting | Default | Description |
|---|---|---|
| `MODEL` | `qwen3:14b` | Ollama model name |
| `AGENT_NAME` | `Jarvis` | Wake word and assistant name |
| `USER_NAME` | `Peyman` | Injected into the system prompt |
| `WAKE_WORD` | `jarvis` | Substring matched in transcripts |
| `PTT_KEY` | `ctrl+space` | Push-to-talk key combination |
| `TTS_ENGINE` | `kokoro` | `"kokoro"` or `"piper"` |
| `KOKORO_VOICE` | `bm_george` | Kokoro voice ID |
| `VOICE_MODEL` | `en_GB-jenny_dioco-medium` | Piper voice (no `.onnx`) |
| `ALLOW_RUN_COMMANDS` | `True` | Enable PowerShell tool |
| `REQUIRE_CONFIRMATION` | `True` | Voice-confirm before commands |
| `SEARCH_ROOTS` | `["~"]` | Directories the file tools can access |
| `MAX_HISTORY_MESSAGES` | `40` | Conversation turns kept in memory |
| `SYSTEM_PROMPT` | *(see file)* | Full agent personality prompt |

---

## Desktop Tools

The LLM can invoke these during a conversation:

| Tool | What it does |
|---|---|
| `open_app` | Launches an app from the configured allow-list |
| `search_files` | Walks `SEARCH_ROOTS` and returns up to 10 matching paths, newest first |
| `read_file` | Returns the first 4 KB of a text file |
| `open_file` | Opens a file or folder with its default Windows app |
| `web_search` | Queries DuckDuckGo and returns top-5 snippets |
| `run_command` | Runs a PowerShell command (requires voice confirmation by default) |

Add new tools by appending to `tools.SCHEMAS` and `tools._DISPATCH` in `app/tools.py`.

---

## Project Layout

```
LocalVoiceAgent/
├── app/
│   ├── main.py        — Agent loop, mode handling, entry point
│   ├── gui.py         — Tkinter window, animated states, button controls
│   ├── orb3d.py       — NumPy/Pillow software 3D ring renderer
│   ├── stt.py         — Microphone capture, silence detection, Whisper transcription
│   ├── tts.py         — Kokoro / Piper synthesis and audio playback
│   ├── llm.py         — Ollama requests, tool-call loop, history management
│   ├── tools.py       — Desktop tool implementations and LLM schemas
│   ├── memory.py      — JSON conversation history persistence
│   └── settings.py    — All configuration constants
├── data/
│   └── history.json   — Persisted conversation (git-ignored)
├── voices/            — Voice model files (git-ignored; use download_voices.py)
├── download_voices.py — Download Kokoro / Piper models from HuggingFace
├── requirements.txt
└── LICENSE
```

---

## Privacy

- Audio is transcribed locally and never written to disk.
- Conversation text is stored in `data/history.json`, bounded by `MAX_HISTORY_MESSAGES`. Clear with `--reset` or the GUI's **Clear** button.
- File tools only access paths under `SEARCH_ROOTS`.
- `run_command` asks for voice confirmation before executing (`REQUIRE_CONFIRMATION = True`).
- Web search sends your query to DuckDuckGo. Everything else is fully offline.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Cannot connect to Ollama` | Run `ollama serve` and confirm the model is pulled |
| No audio input detected | Check Windows microphone permissions and default device |
| Whisper is very slow | Use `MODEL_SIZE = "tiny"` in `stt.py`, or enable GPU |
| TTS silent or crashes | Re-run `download_voices.py`; verify `KOKORO_VOICE` is valid |
| Push-to-talk not responding | Run PowerShell as Administrator (Win32 keyboard hook) |
| Wake word never triggers | Lower `SILENCE_THRESHOLD` in settings, or switch to `--mode ptt` |

---

## Roadmap

- [ ] Reminders and calendar integration
- [ ] Native wake-word model (replace transcription-based detection)
- [ ] Streaming TTS — begin speaking before generation finishes
- [ ] Screen reader tool (OCR + describe what's visible)
- [ ] Plugin system for user-defined tools
- [ ] macOS / Linux support

---

## License

MIT — see [LICENSE](LICENSE).
