# Local Voice Agent - Settings
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen3:14b"
KEEP_ALIVE = "1h"
VOICE_MODE = "local"
ALLOW_FILE_TOOLS = True
REQUIRE_CONFIRMATION = True
SAVE_AUDIO = False

# --- Voice agent behaviour ---
AGENT_NAME = "Jarvis"
USER_NAME = "Peyman"
WAKE_WORD = "jarvis"          # matched against the transcript (e.g. "hey jarvis")
PTT_KEY = "ctrl+space"              # hold to talk in push-to-talk mode
SILENCE_SECONDS = 1.0         # stop recording after this much silence
SILENCE_THRESHOLD = 0.012     # RMS level considered silence; raise if noisy room
MAX_RECORD_SECONDS = 30
HISTORY_FILE = "data/history.json"
MAX_HISTORY_MESSAGES = 40
ALLOW_RUN_COMMANDS = True     # still asks for confirmation when REQUIRE_CONFIRMATION
ALLOWED_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "vscode": "code",
    "terminal": "wt.exe",
}
SEARCH_ROOTS = ["~"]   # whole user profile; add e.g. "D:/" for other drives
SEARCH_SKIP_DIRS = {"appdata", "node_modules", ".git", "venv", ".venv", "__pycache__",
                    "site-packages", "anaconda3", ".cache", ".claude", "$recycle.bin"}
SEARCH_TIME_LIMIT = 10        # seconds
ALLOW_WEB_SEARCH = True
BLOCKED_OPEN_EXT = {".exe", ".bat", ".cmd", ".ps1", ".msi", ".vbs", ".js", ".scr", ".lnk", ".com"}
SYSTEM_PROMPT = (
    "You are {agent}, a local AI voice assistant for {user}, running on their Windows PC. "
    "Your replies are spoken aloud, so keep them short (1-3 sentences), plain text only, "
    "no markdown, lists or emojis. Use tools when the user asks you to open an app, "
    "find or read files, search the web for current information, or run a command; "
    "after a web search, summarise the answer in a sentence or two instead of reading URLs; "
    "otherwise just answer. Be direct and honest; "
    "if you don't know, say so."
)

VOICE_MODEL = "en_GB-jenny_dioco-medium"   # file name in voices/ (without .onnx)

# TTS engine: "kokoro" (natural, recommended) or "piper"
TTS_ENGINE = "kokoro"
KOKORO_VOICE = "bm_george"   # British female. Others: af_heart, af_bella, af_nicole, bf_isabella, bm_george
KOKORO_SPEED = 1.0

# Spoken once at startup. Set STARTUP_GREETING = "" to just say "<name> online."
STARTUP_GREETING = (
    "Good evening, {user}. {agent} is online. "
    "I can hear you, speak, remember our conversations, open apps, search your files "
    "and run commands with your permission. Say hey {agent} to wake me, and standby to "
    "put me to sleep. Next on the list: web search, reminders and your calendar."
)
