"""Tools the LLM can call. Dangerous ones go through a confirm callback."""
import os, subprocess, time
from app import settings

# set by main.py: callable(prompt: str) -> bool
confirm = lambda prompt: False

SCHEMAS = [
    {"type": "function", "function": {
        "name": "open_app",
        "description": "Open an application on the PC. Known apps: " + ", ".join(settings.ALLOWED_APPS),
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "App name"}}, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "search_files",
        "description": "Search the user's PC for files whose NAME contains the given words. "
                       "Returns up to 10 full paths, newest first.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Words from the file name"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read the start of a text file (txt, md, py, csv, json, log...) given its full path.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "open_file",
        "description": "Open a file or folder with its default app, given its full path.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web for current information, news, facts or how-tos. "
                       "Returns the top results with short snippets.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "run_command",
        "description": "Run a PowerShell command and return its output. Requires user confirmation.",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}}, "required": ["command"]}}},
]


def open_app(name: str) -> str:
    exe = settings.ALLOWED_APPS.get(name.lower().strip())
    if not exe:
        return f"Unknown app '{name}'. Known: {', '.join(settings.ALLOWED_APPS)}"
    try:
        subprocess.Popen(f'start "" "{exe}"', shell=True)
        return f"Opened {name}."
    except Exception as e:
        return f"Failed to open {name}: {e}"


def _under_home(path: str) -> bool:
    roots = [os.path.realpath(os.path.expanduser(r)) for r in settings.SEARCH_ROOTS]
    real = os.path.realpath(os.path.expanduser(path))
    return any(real == r or real.startswith(r + os.sep) for r in roots)


def search_files(query: str) -> str:
    if not settings.ALLOW_FILE_TOOLS:
        return "File tools are disabled in settings (ALLOW_FILE_TOOLS)."
    words = query.lower().split()
    if not words:
        return "Empty query."
    skip = settings.SEARCH_SKIP_DIRS
    deadline = time.time() + settings.SEARCH_TIME_LIMIT
    found = []
    for root in settings.SEARCH_ROOTS:
        for dirpath, dirs, files in os.walk(os.path.expanduser(root)):
            dirs[:] = [d for d in dirs if d.lower() not in skip and not d.startswith(".")]
            for name in files + dirs:
                low = name.lower()
                if all(w in low for w in words):
                    found.append(os.path.join(dirpath, name))
            if time.time() > deadline or len(found) >= 200:
                break
    if not found:
        return "No matching files."
    def mtime(p):
        try:
            return os.path.getmtime(p)
        except OSError:
            return 0
    found.sort(key=mtime, reverse=True)
    return "\n".join(found[:10])


def read_file(path: str) -> str:
    if not settings.ALLOW_FILE_TOOLS:
        return "File tools are disabled in settings."
    if not _under_home(path):
        return "That path is outside the allowed folders."
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        return "File not found."
    try:
        with open(path, "rb") as f:
            raw = f.read(4000)
        if b"\x00" in raw:
            return "That looks like a binary file, so I can't read it as text."
        return raw.decode("utf-8", errors="replace")
    except Exception as e:
        return f"Could not read file: {e}"


def open_file(path: str) -> str:
    if not settings.ALLOW_FILE_TOOLS:
        return "File tools are disabled in settings."
    if not _under_home(path):
        return "That path is outside the allowed folders."
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return "File not found."
    if os.path.splitext(path)[1].lower() in settings.BLOCKED_OPEN_EXT:
        return "I won't open executable or script files."
    try:
        os.startfile(path)
        return f"Opened {os.path.basename(path)}."
    except Exception as e:
        return f"Could not open: {e}"


def web_search(query: str) -> str:
    if not settings.ALLOW_WEB_SEARCH:
        return "Web search is disabled in settings."
    try:
        from ddgs import DDGS
        results = DDGS().text(query, max_results=5)
    except Exception as e:
        return f"Web search failed: {e}"
    if not results:
        return "No results."
    return "\n\n".join(f"{r.get('title', '')}\n{r.get('body', '')}\n{r.get('href', '')}"
                       for r in results)


def run_command(command: str) -> str:
    if not settings.ALLOW_RUN_COMMANDS:
        return "Running commands is disabled in settings."
    if settings.REQUIRE_CONFIRMATION and not confirm(f"Run command: {command}?"):
        return "User declined."
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                           capture_output=True, text=True, timeout=30)
        return (r.stdout + r.stderr).strip()[:1500] or "(no output)"
    except Exception as e:
        return f"Command failed: {e}"


_DISPATCH = {"open_app": open_app, "search_files": search_files, "read_file": read_file,
             "open_file": open_file, "web_search": web_search, "run_command": run_command}


def call(name: str, args: dict) -> str:
    fn = _DISPATCH.get(name)
    if not fn:
        return f"Unknown tool {name}"
    try:
        return fn(**args)
    except TypeError as e:
        return f"Bad arguments: {e}"
