"""Simulated scanning: turn a clean page render into a plausible office scan."""

from __future__ import annotations

import io
import random

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


def scan(page: Image.Image, seed: str) -> bytes:
    """Return JPEG bytes of a degraded greyscale version of ``page``.

    Applied, with per-document random strength: small skew, blur, uneven
    exposure, sensor noise, speckle and JPEG compression.
    """
    rng = random.Random(f"scan:{seed}")
    np_rng = np.random.default_rng(rng.getrandbits(32))
    img = page.convert("L")
    img = img.rotate(rng.uniform(-1.2, 1.2), resample=Image.Resampling.BICUBIC, fillcolor=255)
    if rng.random() < 0.8:
        img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.2, 0.9)))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.75, 1.05))
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.92, 1.04))

    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape
    # Uneven exposure: a gentle gradient across the page.
    gx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    gy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
    arr -= rng.uniform(0, 18) * (rng.uniform(0, 1) * gx + rng.uniform(0, 1) * gy)
    arr += np_rng.normal(0, rng.uniform(2, 9), size=arr.shape).astype(np.float32)
    n_speckles = int(h * w * rng.uniform(0, 4e-5))
    ys, xs = np_rng.integers(0, h, n_speckles), np_rng.integers(0, w, n_speckles)
    arr[ys, xs] = np_rng.integers(0, 80, n_speckles)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="L")

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=rng.randint(55, 85), optimize=True)
    return out.getvalue()
