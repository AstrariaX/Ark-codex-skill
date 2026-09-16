import math
import os
import struct
import wave

from config import SOUNDS_DIR


def _generate_wav(path, freq, duration, volume=0.5):
    sample_rate = 22050
    n_samples = int(sample_rate * duration)
    with wave.open(path, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        for i in range(n_samples):
            t = i / sample_rate
            envelope = max(0.0, 1.0 - t / duration)
            val = int(volume * envelope * 32767 * math.sin(2 * math.pi * freq * t))
            f.writeframes(struct.pack("<h", max(-32768, min(32767, val))))


def ensure_sounds():
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    drop_path = os.path.join(SOUNDS_DIR, "drop.wav")
    click_path = os.path.join(SOUNDS_DIR, "click.wav")
    if not os.path.isfile(drop_path):
        _generate_wav(drop_path, 80, 0.15, 0.6)
    if not os.path.isfile(click_path):
        _generate_wav(click_path, 800, 0.08, 0.4)
    return drop_path, click_path
