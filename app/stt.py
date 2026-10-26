import sounddevice as sd
import numpy as np
import tempfile, os, soundfile as sf
from faster_whisper import WhisperModel

# Load model once at import - tiny.en is fast; swap for "base.en" for more accuracy
_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

SAMPLE_RATE = 16000

def record(seconds: int = 5) -> np.ndarray:
    """Record audio from the default microphone."""
    print(f"  [STT] Recording for {seconds}s...")
    audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                   channels=1, dtype="float32")
    sd.wait()
    return audio.flatten()

def transcribe(audio: np.ndarray) -> str:
    """Transcribe a numpy float32 array (16 kHz mono)."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_path = f.name
    try:
        sf.write(tmp_path, audio, SAMPLE_RATE)
        segments, _ = _model.transcribe(tmp_path, beam_size=5, language="en")
        text = " ".join(seg.text for seg in segments).strip()
        return text
    finally:
        os.unlink(tmp_path)

def listen(seconds: int = 5) -> str:
    """Record then transcribe. Returns transcript string."""
    audio = record(seconds)
    return transcribe(audio)


# ---------------------------------------------------------------------------
# Silence-detected recording, push-to-talk, wake word
# ---------------------------------------------------------------------------
from app import settings

_BLOCK = int(SAMPLE_RATE * 0.05)  # 50 ms blocks


level = 0.0  # latest mic loudness, read by the GUI
import threading
interrupt = threading.Event()  # set by the UI to break out of a blocking listen


def _rms(block: np.ndarray) -> float:
    global level
    level = float(np.sqrt(np.mean(block ** 2)))
    return level


PREROLL_BLOCKS = 12  # 0.6 s of audio kept from before speech is detected


def record_until_silence(wait_for_speech: float = 8.0) -> np.ndarray:
    """Record until the speaker pauses for SILENCE_SECONDS.

    A rolling pre-roll buffer is prepended so the first syllable isn't clipped.
    Gives up (returns empty) if no speech starts within wait_for_speech seconds.
    """
    from collections import deque
    preroll = deque(maxlen=PREROLL_BLOCKS)
    chunks, started, silent_blocks = [], False, 0
    silence_limit = int(settings.SILENCE_SECONDS / 0.05)
    max_blocks = int(settings.MAX_RECORD_SECONDS / 0.05)
    wait_blocks = int(wait_for_speech / 0.05)
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        blocksize=_BLOCK) as stream:
        for i in range(max(max_blocks, wait_blocks)):
            if interrupt.is_set():
                return np.zeros(0, dtype="float32")
            block, _ = stream.read(_BLOCK)
            block = block.flatten()
            loud = _rms(block) > settings.SILENCE_THRESHOLD
            if not started:
                if loud:
                    started, silent_blocks = True, 0
                    chunks = list(preroll) + [block]
                else:
                    preroll.append(block)
                    if i >= wait_blocks:
                        break
                continue
            chunks.append(block)
            silent_blocks = 0 if loud else silent_blocks + 1
            if silent_blocks >= silence_limit or len(chunks) >= max_blocks:
                break
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype="float32")


_VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12, "space": 0x20,
       **{chr(c): c for c in range(0x30, 0x3A)},
       **{chr(c).lower(): c for c in range(0x41, 0x5B)},
       **{f"f{n}": 0x6F + n for n in range(1, 13)}}


def _combo_down() -> bool:
    """True while every key in PTT_KEY (e.g. 'ctrl+space') is held. Uses the
    Win32 API directly, so no keyboard hooks or admin rights are needed."""
    import ctypes
    user32 = ctypes.windll.user32
    keys = [k.strip().lower() for k in settings.PTT_KEY.split("+")]
    return all(user32.GetAsyncKeyState(_VK[k]) & 0x8000 for k in keys)


def record_push_to_talk() -> np.ndarray:
    """Wait for PTT_KEY, record while held, return audio.

    The mic stream is opened while waiting and the last 0.6 s is kept, so
    audio from just before the key press (and stream start-up lag) isn't lost.
    """
    import time
    from collections import deque
    preroll = deque(maxlen=PREROLL_BLOCKS)
    chunks = []
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                        blocksize=_BLOCK) as stream:
        while not _combo_down():
            block, _ = stream.read(_BLOCK)
            preroll.append(block.flatten())
        print("  [STT] Listening (release key to send)...")
        chunks = list(preroll)
        while _combo_down():
            block, _ = stream.read(_BLOCK)
            chunks.append(block.flatten())
            _rms(chunks[-1])
    print(f"  [STT] Captured {len(chunks) * 0.05:.1f}s")
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype="float32")


def wait_for_wake_word() -> str:
    """Block until the wake word is heard. Returns any command spoken after it
    in the same breath (e.g. "hey jarvis open notepad"), else ''."""
    print(f"  [WAKE] Say 'Hey {settings.AGENT_NAME}'...")
    while True:
        if interrupt.is_set():
            return ""
        audio = record_until_silence(wait_for_speech=30)
        if len(audio) < SAMPLE_RATE * 0.3:
            continue
        text = transcribe(audio)
        low = text.lower()
        # Whisper may mis-spell the name
        for variant in (settings.WAKE_WORD, "jervis", "jarvus"):
            idx = low.find(variant)
            if idx != -1:
                return text[idx + len(variant):].strip(" ,.!?")


def calibrate(seconds: float = 1.5) -> float:
    """Measure room noise and set SILENCE_THRESHOLD relative to it, so quiet
    or low-gain microphones still trigger recording."""
    audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                   channels=1, dtype="float32")
    sd.wait()
    noise = _rms(audio.flatten())
    settings.SILENCE_THRESHOLD = min(max(noise * 3, 0.002), 0.012)
    print(f"  [STT] Room noise {noise:.4f} -> threshold {settings.SILENCE_THRESHOLD:.4f}")
    return settings.SILENCE_THRESHOLD
