"""
Image pre-processing utilities.

Normalises uploads before they hit the Gemini API:
  • Resize to max dimension (keeps aspect ratio)
  • Convert to PNG (consistent format)
  • Strip EXIF / metadata
"""

from __future__ import annotations

import io
from PIL import Image

from app.config import get_settings


def preprocess(raw_bytes: bytes) -> bytes:
    """Return a cleaned PNG buffer ready for the Gemini API."""
    settings = get_settings()
    img = Image.open(io.BytesIO(raw_bytes))

    # Strip EXIF orientation and flatten alpha
    img = img.convert("RGB")

    # Resize longest side to MAX_IMAGE_DIM, keep ratio
    max_dim = settings.max_image_dim
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def get_dimensions(raw_bytes: bytes) -> tuple[int, int]:
    """Return (width, height) of an image."""
    img = Image.open(io.BytesIO(raw_bytes))
    return img.size
