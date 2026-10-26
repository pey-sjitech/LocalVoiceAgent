"""Download voice model files into the voices/ directory.

Kokoro ONNX (recommended, ~340 MB total):
  kokoro-v1.0.onnx + voices-v1.0.bin  — from huggingface.co/hexgrad/Kokoro-82M

Piper voices (~61 MB each, used as fallback):
  en_GB-jenny_dioco-medium  — British female
  en_US-amy-medium          — US female
  en_US-ryan-high           — US male, high quality

Usage:
  python download_voices.py            # Kokoro only (default TTS engine)
  python download_voices.py --all      # Kokoro + all Piper voices
  python download_voices.py --piper    # Piper voices only
"""
import argparse
import os
import urllib.request

VOICES_DIR = os.path.join(os.path.dirname(__file__), "voices")

KOKORO = [
    (
        "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/kokoro-v1.0.onnx",
        "kokoro-v1.0.onnx",
    ),
    (
        "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices-v1.0.bin",
        "voices-v1.0.bin",
    ),
]

PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

PIPER = [
    (f"{PIPER_BASE}/en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium.onnx",
     "en_GB-jenny_dioco-medium.onnx"),
    (f"{PIPER_BASE}/en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium.onnx.json",
     "en_GB-jenny_dioco-medium.onnx.json"),
    (f"{PIPER_BASE}/en/en_US/amy/medium/en_US-amy-medium.onnx",
     "en_US-amy-medium.onnx"),
    (f"{PIPER_BASE}/en/en_US/amy/medium/en_US-amy-medium.onnx.json",
     "en_US-amy-medium.onnx.json"),
    (f"{PIPER_BASE}/en/en_US/ryan/high/en_US-ryan-high.onnx",
     "en_US-ryan-high.onnx"),
    (f"{PIPER_BASE}/en/en_US/ryan/high/en_US-ryan-high.onnx.json",
     "en_US-ryan-high.onnx.json"),
]


def _download(url: str, dest: str) -> None:
    os.makedirs(VOICES_DIR, exist_ok=True)
    path = os.path.join(VOICES_DIR, dest)
    if os.path.exists(path):
        print(f"  already exists: {dest}")
        return
    print(f"  downloading {dest} ...", end="", flush=True)

    def _progress(count, block, total):
        if total > 0:
            pct = min(count * block * 100 // total, 100)
            print(f"\r  downloading {dest} ... {pct}%", end="", flush=True)

    urllib.request.urlretrieve(url, path, reporthook=_progress)
    print(f"\r  downloaded  {dest}  ({os.path.getsize(path) // 1_048_576} MB)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Download LocalVoiceAgent voice models.")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--all", action="store_true", help="Kokoro + all Piper voices")
    grp.add_argument("--piper", action="store_true", help="Piper voices only")
    args = ap.parse_args()

    if args.piper:
        files = PIPER
    elif args.all:
        files = KOKORO + PIPER
    else:
        files = KOKORO

    print(f"Saving to: {VOICES_DIR}\n")
    for url, dest in files:
        _download(url, dest)
    print("\nDone. Edit TTS_ENGINE in app/settings.py to switch between 'kokoro' and 'piper'.")


if __name__ == "__main__":
    main()
