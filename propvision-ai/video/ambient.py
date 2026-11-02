"""Built-in background music: a soft ambient pad synthesised with NumPy.

This is generated from scratch (sine waves + envelopes), so there are no copyright or
licensing concerns. It is intentionally simple, calm background audio - not a composed track.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 32000

# A-minor-ish progression: Am - F - C - G (root, third, fifth) in Hz.
CHORDS = [
    (110.00, 130.81, 164.81, 220.00),   # Am
    (87.31, 110.00, 130.81, 174.61),    # F
    (130.81, 164.81, 196.00, 261.63),   # C
    (98.00, 123.47, 146.83, 196.00),    # G
]


def synthesize_ambient(seconds: float, chord_seconds: float = 6.0) -> np.ndarray:
    """Return a stereo float32 array (n, 2) in [-1, 1]."""
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    left = np.zeros(n)
    right = np.zeros(n)
    rng = np.random.default_rng(7)

    chord_count = int(np.ceil(seconds / chord_seconds)) + 1
    for index in range(chord_count):
        start = index * chord_seconds
        # each chord overlaps the next by 2 seconds for a smooth crossfade
        length = chord_seconds + 2.0
        i0 = int(start * SAMPLE_RATE)
        i1 = min(n, int((start + length) * SAMPLE_RATE))
        if i0 >= n:
            break
        local = np.arange(i1 - i0) / SAMPLE_RATE
        env = np.minimum(1.0, local / 2.0) * np.minimum(1.0, (length - local) / 2.0)
        env = np.clip(env, 0, 1) ** 1.5
        for freq in CHORDS[index % len(CHORDS)]:
            for detune, pan in ((-0.6, 0.35), (0.0, 0.5), (0.7, 0.65)):
                f = freq * (1 + detune / 100)
                phase = rng.uniform(0, 2 * np.pi)
                wobble = 1 + 0.15 * np.sin(2 * np.pi * 0.17 * (t[i0:i1]) + phase)
                tone = np.sin(2 * np.pi * f * t[i0:i1] + phase) * 0.5
                tone += np.sin(2 * np.pi * 2 * f * t[i0:i1] + phase) * 0.12
                tone *= env * wobble
                left[i0:i1] += tone * (1 - pan)
                right[i0:i1] += tone * pan

    stereo = np.stack([left, right], axis=1)
    peak = np.max(np.abs(stereo)) or 1.0
    stereo = stereo / peak * 0.5
    fade = int(1.5 * SAMPLE_RATE)
    if n > 2 * fade:
        ramp = np.linspace(0, 1, fade)[:, None]
        stereo[:fade] *= ramp
        stereo[-fade:] *= ramp[::-1]
    return stereo.astype(np.float32)


def write_ambient_wav(path: str | Path, seconds: float) -> Path:
    """Write the ambient pad as a 16-bit stereo WAV and return the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = synthesize_ambient(seconds)
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(pcm.tobytes())
    return path
