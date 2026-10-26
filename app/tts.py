import io, wave, os
import sounddevice as sd
import numpy as np
from piper import PiperVoice
from app import settings

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VOICE_PATH = os.path.join(_BASE, "voices", settings.VOICE_MODEL + ".onnx")
_voice = None

def _get_voice():
    global _voice
    if _voice is None:
        _voice = PiperVoice.load(_VOICE_PATH)
    return _voice

_kokoro = None
_out = None  # persistent output stream: opening a device per phrase adds lag
_KOKORO_RATE = 24000


def _get_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        _kokoro = Kokoro(os.path.join(_BASE, "voices", "kokoro-v1.0.onnx"),
                         os.path.join(_BASE, "voices", "voices-v1.0.bin"))
    return _kokoro


def _get_out():
    global _out
    if _out is None:
        _out = sd.OutputStream(samplerate=_KOKORO_RATE, channels=1, dtype="float32")
        _out.start()
    return _out


def _synth(text: str) -> np.ndarray:
    lang = "en-gb" if settings.KOKORO_VOICE.startswith("b") else "en-us"
    samples, _ = _get_kokoro().create(text, voice=settings.KOKORO_VOICE,
                                      speed=settings.KOKORO_SPEED, lang=lang)
    return samples.astype(np.float32)


def _sentences(text: str):
    import re
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
    # merge tiny fragments so we don't synthesise "Hi." on its own
    out = []
    for p in parts:
        if out and len(out[-1]) < 25:
            out[-1] += " " + p
        else:
            out.append(p)
    return out or [text]


def _speak_kokoro(text: str) -> None:
    """Pipeline: a worker synthesises sentence N+1 while sentence N is playing,
    so speech starts after the first sentence rather than the whole reply."""
    import queue, threading
    q = queue.Queue(maxsize=2)

    def producer():
        try:
            for sent in _sentences(text):
                q.put(_synth(sent))
        finally:
            q.put(None)

    threading.Thread(target=producer, daemon=True).start()
    out = _get_out()
    while True:
        chunk = q.get()
        if chunk is None:
            break
        out.write(chunk)
    out.write(np.zeros(int(_KOKORO_RATE * 0.15), dtype=np.float32))  # flush tail


def warmup() -> None:
    """Load the model and open the audio device ahead of the first phrase."""
    if settings.TTS_ENGINE == "kokoro":
        _synth("Ready.")
        _get_out()
    else:
        _get_voice()


def speak(text: str) -> None:
    if settings.TTS_ENGINE == "kokoro":
        return _speak_kokoro(text)
    voice = _get_voice()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        voice.synthesize_wav(text, out)
    buf.seek(0)
    with wave.open(buf, "rb") as wav:
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(audio, samplerate=rate)
    sd.wait()
