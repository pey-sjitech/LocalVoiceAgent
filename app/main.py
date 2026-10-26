"""Entry point.

  python -m app.main            -> window UI, voice activated ("Hey Jarvis")
  python -m app.main --cli      -> terminal only
  python -m app.main --mode ptt|wake|always  --reset
"""
import argparse, os, sys
if __package__ in (None, ""):  # allow `python app/main.py`
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import settings

stt = tts = llm = memory = tools = None


def _load():
    """Import the heavy modules (Whisper etc.) lazily so the window opens first."""
    global stt, tts, llm, memory, tools
    from app import stt, tts, llm, memory, tools  # noqa: F811


# Wake-word mode has two states: standby (needs "Hey Jarvis") and active
# (keeps listening for follow-ups until told to stand by). The UI can flip it.
session = {"active": False}
STANDBY_PHRASES = ("standby", "stand by", "go to standby", "go to sleep",
                   "go to sleep mode", "that's all", "that is all", "sleep mode")


def set_active(on: bool):
    session["active"] = on
    stt.interrupt.set()  # break a blocking wake-word wait so the change applies now


def _noop(kind, text=""):
    pass


def voice_confirm(prompt: str, emit=_noop) -> bool:
    emit("assistant", prompt)
    emit("state", "speaking")
    tts.speak(prompt)
    emit("state", "listening")
    audio = stt.record_until_silence(wait_for_speech=6)
    answer = stt.transcribe(audio).lower() if len(audio) else ""
    emit("user", f"({answer or 'no answer'})")
    return any(w in answer for w in ("yes", "yeah", "sure", "do it", "confirm", "go ahead"))


def get_utterance(mode: str, emit) -> str:
    if mode == "ptt":
        emit("state", "idle")
        audio = stt.record_push_to_talk()
        emit("state", "thinking")
        return stt.transcribe(audio) if len(audio) > stt.SAMPLE_RATE * 0.3 else ""
    if mode == "wake" and not session["active"]:
        emit("state", "sleeping")
        stt.interrupt.clear()
        inline = stt.wait_for_wake_word()
        if stt.interrupt.is_set():          # UI toggled while waiting
            stt.interrupt.clear()
            if not session["active"]:
                return ""
            inline = ""
        else:
            session["active"] = True
        if inline:
            return inline
        emit("state", "speaking")
        tts.speak("Yes?")
    stt.interrupt.clear()
    emit("state", "listening")
    audio = stt.record_until_silence()
    emit("state", "thinking")
    return stt.transcribe(audio) if len(audio) else ""


def run_agent(mode: str, emit=_noop, get_mode=None):
    """Main loop. `emit(kind, text)` reports state/user/assistant/system events.
    `get_mode()` (optional) lets the UI change the mode while running."""
    emit("system", "Loading models...")
    _load()
    # Warm everything up now so the first reply isn't slow: TTS model + audio
    # device, and the LLM (loaded into memory by a throwaway request).
    import threading
    threading.Thread(target=llm.warm, daemon=True).start()
    tts.warmup()
    stt.calibrate()
    tools.confirm = lambda p: voice_confirm(p, emit)
    greeting = (settings.STARTUP_GREETING or "{agent} online.").format(
        agent=settings.AGENT_NAME, user=settings.USER_NAME)
    emit("assistant", greeting)
    emit("state", "speaking")
    tts.speak(greeting)
    while True:
        m = get_mode() if get_mode else mode
        text = get_utterance(m, emit)
        if not text:
            continue
        if m == "wake" and text.lower().strip(" .!,?'") in STANDBY_PHRASES:
            session["active"] = False
            emit("user", text)
            emit("system", "Standby")
            emit("state", "speaking")
            tts.speak("Standing by.")
            continue
        emit("user", text)
        if text.lower().strip(" .!") in ("forget everything", "reset memory"):
            memory.clear()
            llm.conversation_history.clear()
            emit("system", "Memory cleared.")
            emit("state", "speaking")
            tts.speak("Memory cleared.")
            continue
        emit("state", "thinking")
        reply = llm.chat(text)
        emit("assistant", reply)
        emit("state", "speaking")
        tts.speak(reply)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["ptt", "wake", "always"], default="wake")
    ap.add_argument("--reset", action="store_true", help="forget saved conversation")
    ap.add_argument("--cli", action="store_true", help="terminal only, no window")
    args = ap.parse_args()
    if args.reset:
        from app import memory as _m
        _m.clear()

    if not args.cli:
        from app.gui import launch
        return launch(args.mode)

    def emit(kind, text=""):
        if kind == "state":
            return
        print(f"[{kind}] {text}")

    try:
        run_agent(args.mode, emit)
    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()
