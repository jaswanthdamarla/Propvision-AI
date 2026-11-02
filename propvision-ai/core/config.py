"""Central configuration: paths, limits, option tables and environment handling."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ASSETS_DIR = PROJECT_ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
MUSIC_DIR = ASSETS_DIR / "music"
SAMPLE_DIR = PROJECT_ROOT / "sample_data"
UPLOADS_DIR = PROJECT_ROOT / "uploads"
OUTPUT_DIR = PROJECT_ROOT / "output"

# --- Image / input limits --------------------------------------------------
ALLOWED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
ALLOWED_MUSIC_EXTENSIONS = (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")
MIN_IMAGES = 4
MAX_IMAGES = 8
MAX_IMAGE_BYTES = 30 * 1024 * 1024
MAX_IMAGE_PIXELS = 64_000_000        # hard reject above this (e.g. 8000x8000)
MIN_IMAGE_SIDE = 320                 # hard reject below this
RECOMMENDED_IMAGE_SIDE = 720         # warn below this
MAX_MUSIC_BYTES = 40 * 1024 * 1024

MAX_TITLE_CHARS = 80
MAX_LOCATION_CHARS = 80
MAX_PRICE_CHARS = 40
MAX_AREA_CHARS = 40
MAX_DESCRIPTION_CHARS = 600
MAX_CONTACT_CHARS = 80
MAX_CTA_CHARS = 90
MAX_AMENITIES = 12
MAX_AMENITY_CHARS = 60

# --- Creative options ------------------------------------------------------
PROPERTY_CATEGORIES = [
    "Apartment", "Villa", "Independent House", "Penthouse", "Townhouse",
    "Studio", "Farmhouse", "Commercial Property", "Office Space", "Shop",
    "Land / Plot", "Other",
]
# Categories where bedrooms / bathrooms make sense.
RESIDENTIAL_CATEGORIES = {
    "Apartment", "Villa", "Independent House", "Penthouse", "Townhouse",
    "Studio", "Farmhouse",
}

ASPECT_RATIOS = {
    "Vertical 9:16 (Reels / Shorts)": "9:16",
    "Landscape 16:9 (YouTube / Presentations)": "16:9",
}
RESOLUTIONS = {"720p": "720p", "1080p": "1080p"}
VIDEO_SIZES = {
    ("9:16", "720p"): (720, 1280),
    ("9:16", "1080p"): (1080, 1920),
    ("16:9", "720p"): (1280, 720),
    ("16:9", "1080p"): (1920, 1080),
}
DURATIONS = (20, 30, 40)
FPS = 30

THEME_NAMES = [
    "Luxury Editorial",
    "Modern Minimal",
    "Warm & Welcoming",
    "Bold Contemporary",
]

# --- Environment -----------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def gemini_api_key() -> str:
    """Return the Gemini API key from the environment (never hardcoded)."""
    return os.getenv("GEMINI_API_KEY", "").strip()


def find_ffmpeg() -> str:
    """Locate an ffmpeg binary: $FFMPEG_BINARY, imageio-ffmpeg, then PATH.

    Raises RuntimeError with a helpful message when none is available.
    """
    env_path = os.getenv("FFMPEG_BINARY", "").strip()
    if env_path and Path(env_path).exists():
        return env_path
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:  # pragma: no cover - depends on the environment
        pass
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    raise RuntimeError(
        "FFmpeg was not found. Run `pip install -r requirements.txt` "
        "(installs imageio-ffmpeg) or install FFmpeg (macOS: `brew install ffmpeg`)."
    )


def ensure_dirs() -> None:
    for directory in (UPLOADS_DIR, OUTPUT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
