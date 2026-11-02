"""Glue between the UI and the engines: file handling, music preparation, output naming."""
from __future__ import annotations

import io
import re
import shutil
import time
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from . import config
from .models import PropertyInfo
from .validator import validate_music


def slugify(text: str, fallback: str = "property") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug[:40] or fallback


def thumbnail_bytes(data: bytes, size: int = 360) -> bytes:
    """Small JPEG preview (EXIF-rotated) for the photo grid."""
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        img.thumbnail((size, size), Image.LANCZOS)
        if img.mode != "RGB":
            img = img.convert("RGB")
        buffer = io.BytesIO()
        img.save(buffer, "JPEG", quality=82)
        return buffer.getvalue()


def save_photos(photos: list[tuple[str, bytes]], session_id: str) -> list[str]:
    """Write uploaded photos to ``uploads/<session>/NN_name`` preserving order; return paths."""
    folder = config.UPLOADS_DIR / session_id
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index, (name, data) in enumerate(photos, start=1):
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(name).name) or f"photo{index}.jpg"
        target = folder / f"{index:02d}_{safe}"
        target.write_bytes(data)
        paths.append(str(target))
    return paths


def prepare_music(mode: str, session_id: str, duration: int,
                  upload: Optional[tuple[str, bytes]] = None) -> tuple[Optional[str], list[str]]:
    """Return (music file path or None, warnings) for the chosen music mode."""
    warnings: list[str] = []
    folder = config.UPLOADS_DIR / session_id
    folder.mkdir(parents=True, exist_ok=True)
    if mode == "ambient":
        from video.ambient import write_ambient_wav

        path = write_ambient_wav(folder / f"ambient_{duration + 4}s.wav", duration + 4)
        return str(path), warnings
    if mode == "upload":
        if upload is None:
            warnings.append("No music file was uploaded, so the video will have no music.")
            return None, warnings
        name, data = upload
        check = validate_music(name, data=data)
        if not check.ok:
            warnings.extend(check.errors)
            warnings.append("The video will be rendered without music.")
            return None, warnings
        warnings.extend(check.warnings)
        target = folder / ("music" + Path(name).suffix.lower())
        target.write_bytes(data)
        return str(target), warnings
    return None, warnings


def output_path_for(info: PropertyInfo) -> Path:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return config.OUTPUT_DIR / f"propvision_{slugify(info.display_title)}_{stamp}.mp4"


def cleanup_old_uploads(max_age_hours: int = 24) -> None:
    """Remove stale per-session upload folders so the uploads directory does not grow forever."""
    if not config.UPLOADS_DIR.exists():
        return
    cutoff = time.time() - max_age_hours * 3600
    for child in config.UPLOADS_DIR.iterdir():
        try:
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            continue
