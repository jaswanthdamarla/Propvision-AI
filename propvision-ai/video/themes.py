"""Visual themes for the video renderer."""
from __future__ import annotations

from dataclasses import dataclass

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Theme:
    name: str
    title_font: str
    body_font: str
    label_font: str
    accent: RGB
    text: RGB
    tint: RGB                   # colour of the readability gradient
    caption_style: str          # "editorial" | "minimal" | "warm" | "bold"
    transition: str             # "crossfade" | "slide"
    transition_seconds: float
    zoom_intensity: float       # extra zoom factor over a scene (0.10 = +10 %)
    gradient_strength: float    # 0..1 maximum opacity of the bottom gradient
    contrast: float = 1.0
    saturation: float = 1.0
    brightness: float = 1.0
    warmth: float = 0.0         # blend with warm colour (0..0.2)
    uppercase_titles: bool = False
    label_tracking: float = 0.18


THEMES: dict[str, Theme] = {
    "Luxury Editorial": Theme(
        name="Luxury Editorial", title_font="lora_bold", body_font="poppins_light", label_font="poppins_medium",
        accent=(212, 175, 105), text=(250, 247, 240), tint=(8, 9, 14), caption_style="editorial",
        transition="crossfade", transition_seconds=0.9, zoom_intensity=0.12, gradient_strength=0.90,
        contrast=1.06, saturation=0.95, brightness=0.97,
    ),
    "Modern Minimal": Theme(
        name="Modern Minimal", title_font="poppins_medium", body_font="poppins_light", label_font="poppins_medium",
        accent=(125, 211, 200), text=(255, 255, 255), tint=(10, 12, 18), caption_style="minimal",
        transition="crossfade", transition_seconds=0.7, zoom_intensity=0.09, gradient_strength=0.75,
        contrast=1.03, saturation=0.98,
    ),
    "Warm & Welcoming": Theme(
        name="Warm & Welcoming", title_font="poppins_bold", body_font="poppins", label_font="poppins_medium",
        accent=(242, 166, 90), text=(255, 250, 242), tint=(34, 18, 8), caption_style="warm",
        transition="crossfade", transition_seconds=0.8, zoom_intensity=0.11, gradient_strength=0.82,
        contrast=1.03, saturation=1.08, brightness=1.02, warmth=0.07,
    ),
    "Bold Contemporary": Theme(
        name="Bold Contemporary", title_font="poppins_bold", body_font="poppins_medium", label_font="poppins_bold",
        accent=(198, 255, 61), text=(255, 255, 255), tint=(0, 0, 0), caption_style="bold",
        transition="slide", transition_seconds=0.5, zoom_intensity=0.17, gradient_strength=0.88,
        contrast=1.12, saturation=1.12, uppercase_titles=True, label_tracking=0.12,
    ),
}


def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES["Luxury Editorial"])
