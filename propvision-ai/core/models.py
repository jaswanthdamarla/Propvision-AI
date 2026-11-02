"""Plain data structures shared between the UI, content engine and renderer."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

from . import config


def parse_amenities(raw: str) -> list[str]:
    """Split free text (commas, semicolons, new lines, bullets) into a clean list."""
    if not raw:
        return []
    parts = re.split(r"[,;\n•|]+", raw)
    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        item = re.sub(r"^[\s\-–—*·\d.)]+", "", part).strip()
        item = re.sub(r"\s+", " ", item)
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


@dataclass
class PropertyInfo:
    title: str = ""
    location: str = ""
    price: str = ""
    category: str = "Apartment"
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area: str = ""
    description: str = ""
    amenities: list[str] = field(default_factory=list)
    contact: str = ""
    cta_text: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "PropertyInfo":
        amenities = data.get("amenities", [])
        if isinstance(amenities, str):
            amenities = parse_amenities(amenities)
        return cls(
            title=str(data.get("title", "") or "").strip(),
            location=str(data.get("location", "") or "").strip(),
            price=str(data.get("price", "") or "").strip(),
            category=str(data.get("category", "") or "Apartment").strip(),
            bedrooms=_to_int(data.get("bedrooms")),
            bathrooms=_to_int(data.get("bathrooms")),
            area=str(data.get("area", "") or "").strip(),
            description=str(data.get("description", "") or "").strip(),
            amenities=[str(a).strip() for a in amenities if str(a).strip()],
            contact=str(data.get("contact", "") or "").strip(),
            cta_text=str(data.get("cta_text", "") or "").strip(),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def is_residential(self) -> bool:
        return self.category in config.RESIDENTIAL_CATEGORIES

    @property
    def display_title(self) -> str:
        """Title with a neutral fallback so a missing title never breaks the video."""
        if self.title:
            return self.title
        if self.location:
            return f"{self.category} in {self.location}"
        return f"Featured {self.category}"


def _to_int(value) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


@dataclass
class SceneSpec:
    """One scene of the storyboard."""
    kind: str                 # "intro" | "photo" | "cta"
    photo_index: int          # index into the uploaded photo list
    duration: float           # nominal seconds (transition overlap excluded)
    reuse: bool = False       # photo already shown earlier -> use a different crop/motion
    label: str = ""           # e.g. "Scene 2 - Photo 3"


@dataclass
class SceneContent:
    kind: str
    caption: str
    sub_caption: str = ""


@dataclass
class GeneratedContent:
    headline: str
    hook: str
    script: str
    scene_captions: list[str]
    closing: str
    social_description: str
    engine: str = "rule-based"   # "rule-based" | "gemini"
    engine_detail: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class RenderSettings:
    aspect: str = "9:16"
    resolution: str = "720p"
    duration: int = 30
    theme: str = "Luxury Editorial"
    music_path: Optional[str] = None      # uploaded or generated audio file
    disclaimer: str = ""                  # optional small note shown on every scene
    fps: int = config.FPS

    @property
    def size(self) -> tuple[int, int]:
        return config.VIDEO_SIZES[(self.aspect, self.resolution)]


@dataclass
class RenderResult:
    path: str
    duration: float
    width: int
    height: int
    fps: int
    size_bytes: int
    scenes: int
    photos_used: int
    has_audio: bool
    warnings: list[str] = field(default_factory=list)
