"""Input validation for property details, photographs and music files.

All functions return a ``ValidationResult`` instead of raising, so the UI can show
useful messages and carry on.
"""
from __future__ import annotations

import io
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, UnidentifiedImageError

from . import config
from .models import PropertyInfo


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        return self


# --------------------------------------------------------------------------
# Property details
# --------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_property(info: PropertyInfo) -> ValidationResult:
    """Validate property details. Only 'nothing to talk about' is a hard error."""
    result = ValidationResult()

    if not info.title and not info.location:
        result.errors.append(
            "Please enter a property title or a location - the video needs at least "
            "one of them to introduce the property."
        )
    if not info.title and info.location:
        result.warnings.append(
            "No property title entered - the video will use a neutral title based on "
            "the category and location."
        )
    if not info.location:
        result.warnings.append("No location entered - location will be left out of the video.")
    if not info.price:
        result.warnings.append("No price entered - the price will be left out of the video.")
    if not info.contact:
        result.warnings.append(
            "No contact details entered - the closing scene will use a generic call to action."
        )

    limits = (
        ("Title", info.title, config.MAX_TITLE_CHARS),
        ("Location", info.location, config.MAX_LOCATION_CHARS),
        ("Price", info.price, config.MAX_PRICE_CHARS),
        ("Area", info.area, config.MAX_AREA_CHARS),
        ("Description", info.description, config.MAX_DESCRIPTION_CHARS),
        ("Contact", info.contact, config.MAX_CONTACT_CHARS),
        ("Call-to-action text", info.cta_text, config.MAX_CTA_CHARS),
    )
    for name, value, limit in limits:
        if len(value) > limit:
            result.errors.append(f"{name} is too long ({len(value)} characters, maximum {limit}).")

    if len(info.amenities) > config.MAX_AMENITIES:
        result.errors.append(
            f"Too many amenities ({len(info.amenities)}). Please keep the {config.MAX_AMENITIES} "
            "most important ones."
        )
    for amenity in info.amenities:
        if len(amenity) > config.MAX_AMENITY_CHARS:
            result.errors.append(
                f"Amenity '{amenity[:25]}...' is too long (maximum {config.MAX_AMENITY_CHARS} characters)."
            )

    if info.contact:
        digits = re.sub(r"\D", "", info.contact)
        if "@" in info.contact:
            if not _EMAIL_RE.match(info.contact.strip()):
                result.warnings.append("The contact email address does not look valid.")
        elif len(digits) < 7:
            result.warnings.append(
                "The contact detail does not look like a phone number or email - "
                "it will be shown exactly as typed."
            )

    if info.bedrooms is not None and info.bedrooms > 50:
        result.errors.append("Bedrooms looks too high - please check the number.")
    if info.bathrooms is not None and info.bathrooms > 50:
        result.errors.append("Bathrooms looks too high - please check the number.")
    if not info.is_residential and (info.bedrooms or info.bathrooms):
        result.warnings.append(
            f"Bedrooms/bathrooms are set but the category is '{info.category}'; "
            "they will be ignored for non-residential categories."
        )
    return result


# --------------------------------------------------------------------------
# Images
# --------------------------------------------------------------------------
@dataclass
class ImageCheck:
    name: str
    ok: bool
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    message: str = ""
    warning: str = ""


def check_image(name: str, data: bytes) -> ImageCheck:
    """Validate one uploaded photograph (extension, size, real decodable image, dimensions)."""
    size = len(data)
    ext = Path(name).suffix.lower()
    if ext not in config.ALLOWED_IMAGE_EXTENSIONS:
        shown = ext or "(no extension)"
        return ImageCheck(
            name, False, size_bytes=size,
            message=f"'{name}': unsupported format {shown}. Use JPG, JPEG, PNG or WEBP.",
        )
    if size == 0:
        return ImageCheck(name, False, message=f"'{name}': the file is empty.")
    if size > config.MAX_IMAGE_BYTES:
        return ImageCheck(
            name, False, size_bytes=size,
            message=f"'{name}': file is too large ({size / 1_048_576:.1f} MB, maximum "
                    f"{config.MAX_IMAGE_BYTES // 1_048_576} MB).",
        )
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            width, height = img.size
            img.verify()  # detects truncated / corrupt data without a full decode
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        return ImageCheck(
            name, False, size_bytes=size,
            message=f"'{name}': the file could not be read as an image (it may be corrupt "
                    "or not a real image).",
        )
    if fmt not in {"JPEG", "PNG", "WEBP"}:
        return ImageCheck(
            name, False, size_bytes=size,
            message=f"'{name}': the content is {fmt or 'unknown'}, not JPEG, PNG or WEBP.",
        )
    if width * height > config.MAX_IMAGE_PIXELS:
        return ImageCheck(
            name, False, width, height, size,
            message=f"'{name}': {width}x{height} is too many pixels "
                    f"({width * height / 1e6:.0f} MP, maximum {config.MAX_IMAGE_PIXELS / 1e6:.0f} MP). "
                    "Please resize it first.",
        )
    if min(width, height) < config.MIN_IMAGE_SIDE:
        return ImageCheck(
            name, False, width, height, size,
            message=f"'{name}': {width}x{height} is too small (shortest side must be at least "
                    f"{config.MIN_IMAGE_SIDE}px).",
        )
    warning = ""
    if min(width, height) < config.RECOMMENDED_IMAGE_SIDE:
        warning = (f"'{name}' is low resolution ({width}x{height}); it may look soft in the video. "
                   f"{config.RECOMMENDED_IMAGE_SIDE}px or more on the shortest side is recommended.")
    return ImageCheck(name, True, width, height, size, warning=warning)


def validate_images(items: Iterable[tuple[str, bytes]]) -> tuple[ValidationResult, list[ImageCheck]]:
    """Validate the whole photo set: count (4-8) and each file."""
    items = list(items)
    result = ValidationResult()
    checks = [check_image(name, data) for name, data in items]

    count = len(items)
    if count < config.MIN_IMAGES:
        missing = config.MIN_IMAGES - count
        result.errors.append(
            f"Please upload at least {config.MIN_IMAGES} photographs "
            f"({count} uploaded, {missing} more needed)."
        )
    elif count > config.MAX_IMAGES:
        result.errors.append(
            f"Too many photographs: {count} uploaded, maximum is {config.MAX_IMAGES}. "
            f"Remove {count - config.MAX_IMAGES}."
        )
    for check in checks:
        if not check.ok:
            result.errors.append(check.message)
        elif check.warning:
            result.warnings.append(check.warning)
    return result, checks


# --------------------------------------------------------------------------
# Music
# --------------------------------------------------------------------------
def probe_media(path: str | Path) -> dict:
    """Return basic info about a media file using ``ffmpeg -i`` (no ffprobe needed).

    Keys: ``duration`` (seconds, may be None), ``has_audio``, ``has_video``, ``width``, ``height``.
    """
    ffmpeg = config.find_ffmpeg()
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    text = proc.stderr or ""
    info: dict = {"duration": None, "has_audio": False, "has_video": False, "width": 0, "height": 0}
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if match:
        hours, minutes, seconds = match.groups()
        info["duration"] = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    info["has_audio"] = bool(re.search(r"Stream #\d+:\d+.*Audio:", text))
    video = re.search(r"Stream #\d+:\d+.*Video:.*?,\s*(\d{2,5})x(\d{2,5})", text)
    if video:
        info["has_video"] = True
        info["width"], info["height"] = int(video.group(1)), int(video.group(2))
    return info


def validate_music(name: str, data: Optional[bytes] = None, path: Optional[str | Path] = None) -> ValidationResult:
    """Validate an optional background-music file. Provide either raw bytes or a path.

    Errors here mean "this music cannot be used"; the UI should continue without music.
    """
    result = ValidationResult()
    ext = Path(name).suffix.lower()
    if ext not in config.ALLOWED_MUSIC_EXTENSIONS:
        result.errors.append(
            f"Music file '{name}' has an unsupported format. Use "
            + ", ".join(e.lstrip(".").upper() for e in config.ALLOWED_MUSIC_EXTENSIONS) + "."
        )
        return result

    size = len(data) if data is not None else (Path(path).stat().st_size if path else 0)
    if size == 0:
        result.errors.append(f"Music file '{name}' is empty.")
        return result
    if size > config.MAX_MUSIC_BYTES:
        result.errors.append(
            f"Music file '{name}' is too large ({size / 1_048_576:.1f} MB, maximum "
            f"{config.MAX_MUSIC_BYTES // 1_048_576} MB)."
        )
        return result

    import tempfile

    temp_path: Optional[Path] = None
    try:
        if path is None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as handle:
                handle.write(data or b"")
                temp_path = Path(handle.name)
            path = temp_path
        info = probe_media(path)
        if not info["has_audio"]:
            result.errors.append(
                f"Music file '{name}' does not contain a playable audio stream - it will be ignored."
            )
        elif info["duration"] is not None and info["duration"] < 3:
            result.warnings.append(
                f"Music file '{name}' is very short ({info['duration']:.1f}s); it will be looped."
            )
    except RuntimeError as exc:           # ffmpeg missing
        result.errors.append(str(exc))
    except subprocess.TimeoutExpired:
        result.errors.append(f"Music file '{name}' took too long to analyse and will be ignored.")
    except Exception as exc:               # noqa: BLE001 - never crash the UI on a bad file
        result.errors.append(f"Music file '{name}' could not be analysed: {exc}")
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
    return result
