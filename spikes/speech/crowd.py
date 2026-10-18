"""Procedural stadium sound for the speech spike: background crowd and a goal roar.

Generated from shaped noise, so there's no licensing question. It's a placeholder
to test the mix; a real crowd recording (royalty-free) will sound better.
"""
import numpy as np


def _shaped_noise(n: int, sr: int, rng: np.random.Generator, low: float, high: float, tilt: float) -> np.ndarray:
    """Noise band-limited to [low, high] Hz with a 1/f^tilt spectrum, normalized to peak 1."""
    spectrum = np.fft.rfft(rng.standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1 / sr)
    gain = np.zeros_like(freqs)
    band = (freqs >= low) & (freqs <= high)
    gain[band] = 1 / np.maximum(freqs[band], 1) ** tilt
    # Soft edges so the band doesn't sound like a filter sweep
    gain *= np.clip((freqs - low * 0.7) / (low * 0.3), 0, 1) * np.clip((high * 1.3 - freqs) / (high * 0.3), 0, 1)
    out = np.fft.irfft(spectrum * gain, n)
    return out / (np.abs(out).max() + 1e-9)


def _slow_wobble(n: int, sr: int, rng: np.random.Generator, depth: float, rate_hz: float) -> np.ndarray:
    """Smooth random gain curve around 1.0, like a crowd's natural swell."""
    points = max(4, int(n / sr * rate_hz) + 2)
    curve = np.interp(np.arange(n), np.linspace(0, n, points), rng.uniform(-1, 1, points))
    return 1 + depth * curve


def ambience(seconds: float, sr: int, seed: int = 7) -> np.ndarray:
    """Background crowd murmur for the whole match, peak about 1."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    murmur = _shaped_noise(n, sr, rng, 180, 2500, 0.6) * _slow_wobble(n, sr, rng, 0.25, 0.4)
    chatter = _shaped_noise(n, sr, rng, 500, 1800, 0.2) * _slow_wobble(n, sr, rng, 0.5, 2.5)
    mix = 0.75 * murmur + 0.25 * chatter
    return mix / (np.abs(mix).max() + 1e-9)


def roar(sr: int, seconds: float = 6.0, seed: int = 11) -> np.ndarray:
    """A goal roar: fast swell, held, then a long fade. Brighter than the murmur."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    dark = _shaped_noise(n, sr, rng, 150, 1500, 0.5)
    bright = _shaped_noise(n, sr, rng, 400, 4000, 0.3)
    brightness = np.clip(t / 0.7, 0, 1) * np.clip((seconds - t) / 3.0, 0, 1)
    body = (1 - 0.6 * brightness) * dark + 0.6 * brightness * bright
    envelope = np.clip(t / 0.6, 0, 1) ** 1.5 * np.where(t < 2.5, 1.0, np.exp(-(t - 2.5) / 1.4))
    out = body * envelope * _slow_wobble(n, sr, rng, 0.15, 3)
    return out / (np.abs(out).max() + 1e-9)
