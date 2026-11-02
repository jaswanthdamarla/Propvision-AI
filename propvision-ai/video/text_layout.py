"""Font loading, text wrapping/fitting and pre-rendered text blocks (Pillow)."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from core import config

FONT_FILES = {
    "poppins_light": "Poppins-Light.ttf",
    "poppins": "Poppins-Regular.ttf",
    "poppins_medium": "Poppins-Medium.ttf",
    "poppins_bold": "Poppins-Bold.ttf",
    "lora": "Lora-Variable.ttf",
    "lora_bold": "Lora-Variable.ttf",
}
SYSTEM_FALLBACKS = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",   # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",        # Linux
    "C:/Windows/Fonts/segoeui.ttf",                           # Windows
]


@lru_cache(maxsize=256)
def load_font(key: str, size: int) -> ImageFont.FreeTypeFont:
    size = max(8, int(size))
    filename = FONT_FILES.get(key, FONT_FILES["poppins"])
    path = config.FONTS_DIR / filename
    if path.exists():
        try:
            font = ImageFont.truetype(str(path), size)
            if key.startswith("lora"):
                try:
                    font.set_variation_by_name("Bold" if key == "lora_bold" else "SemiBold")
                except Exception:  # variation support missing -> default weight is fine
                    pass
            return font
        except OSError:
            pass
    for fallback in SYSTEM_FALLBACKS:
        if Path(fallback).exists():
            try:
                return ImageFont.truetype(fallback, size)
            except OSError:
                continue
    return ImageFont.load_default(size)


@lru_cache(maxsize=2048)
def _has_glyph(key: str, size: int, char: str) -> bool:
    font = load_font(key, size)
    try:
        mask = font.getmask(char)
        missing = font.getmask("\U0010FFFF")
    except Exception:
        return True
    return not (mask.size == missing.size and bytes(mask) == bytes(missing))


def font_for(key: str, size: int, text: str) -> ImageFont.FreeTypeFont:
    """Return the requested font, or a Poppins fallback if it lacks a glyph (e.g. the rupee sign)."""
    if all(c.isspace() or _has_glyph(key, size, c) for c in text):
        return load_font(key, size)
    for alt in ("poppins_medium", "poppins"):
        if all(c.isspace() or _has_glyph(alt, size, c) for c in text):
            return load_font(alt, size)
    return load_font(key, size)


def text_width(font: ImageFont.FreeTypeFont, text: str, tracking: float = 0.0) -> float:
    if not text:
        return 0.0
    return font.getlength(text) + tracking * (len(text) - 1)


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: float, tracking: float = 0.0) -> list[str]:
    """Greedy word wrap; words wider than the box are split by character."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if text_width(font, candidate, tracking) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            while text_width(font, word, tracking) > max_width and len(word) > 1:
                cut = len(word)
                while cut > 1 and text_width(font, word[:cut], tracking) > max_width:
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        if current:
            lines.append(current)
    return lines or [""]


def fit_text(text: str, font_key: str, start_size: int, min_size: int, max_width: float,
             max_lines: int, tracking_em: float = 0.0) -> tuple[ImageFont.FreeTypeFont, list[str], float]:
    """Shrink the font until the text fits in ``max_lines`` within ``max_width``.

    Returns (font, lines, tracking_px). The last line is ellipsised if it still overflows.
    """
    size = start_size
    while True:
        font = font_for(font_key, size, text)
        tracking = tracking_em * size
        lines = wrap_text(text, font, max_width, tracking)
        if len(lines) <= max_lines or size <= min_size:
            break
        size = max(min_size, int(size * 0.93))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and text_width(font, last + "…", tracking) > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return font, lines, tracking


@dataclass
class TextBlock:
    """A pre-rendered RGBA image that is faded/slid in at render time."""
    image: Image.Image           # RGBA
    x: int
    y: int
    delay: float = 0.0           # seconds after the scene's text-start
    duration: float = 0.6
    rise: int = 0                # pixels it travels upward while appearing

    def __post_init__(self) -> None:
        self.rgb = self.image.convert("RGB")
        self.alpha = self.image.getchannel("A")

    @property
    def width(self) -> int:
        return self.image.width

    @property
    def height(self) -> int:
        return self.image.height


def _draw_tracked(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str,
                  font: ImageFont.FreeTypeFont, fill, tracking: float) -> None:
    if tracking == 0:
        draw.text(xy, text, font=font, fill=fill)
        return
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += font.getlength(char) + tracking


def render_text_block(lines: list[str], font: ImageFont.FreeTypeFont, fill: tuple[int, int, int],
                      tracking: float = 0.0, line_spacing: float = 1.22, align: str = "left",
                      shadow: bool = True, shadow_strength: float = 0.55,
                      card: Optional[tuple[int, int, int, int]] = None, card_radius: int = 0,
                      card_padding: tuple[int, int] = (0, 0), card_outline: Optional[tuple[int, int, int, int]] = None,
                      outline_width: int = 0, min_width: int = 0) -> Image.Image:
    """Render text (optionally on a rounded card) into a tight RGBA image."""
    ascent, descent = font.getmetrics()
    line_height = int((ascent + descent) * line_spacing)
    widths = [text_width(font, line, tracking) for line in lines]
    content_w = int(max(widths + [min_width])) + 1
    content_h = line_height * len(lines) + int(descent * 0.3)

    pad_x, pad_y = card_padding
    blur = max(2, int(font.size * 0.07))
    margin = blur * 3 if shadow and not card else 0
    total_w = content_w + pad_x * 2 + margin * 2
    total_h = content_h + pad_y * 2 + margin * 2
    img = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))

    if card is not None:
        ImageDraw.Draw(img).rounded_rectangle(
            (margin, margin, total_w - margin - 1, total_h - margin - 1),
            radius=card_radius, fill=card, outline=card_outline, width=outline_width,
        )

    origin_x = margin + pad_x
    origin_y = margin + pad_y

    def positions():
        for index, line in enumerate(lines):
            if align == "center":
                x = origin_x + (content_w - widths[index]) / 2
            elif align == "right":
                x = origin_x + content_w - widths[index]
            else:
                x = origin_x
            yield line, x, origin_y + index * line_height

    if shadow and not card:
        shadow_layer = Image.new("L", img.size, 0)
        sdraw = ImageDraw.Draw(shadow_layer)
        for line, x, y in positions():
            _draw_tracked(sdraw, (x, y + blur * 0.6), line, font, 255, tracking)
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(blur))
        shadow_layer = shadow_layer.point(lambda v: int(v * shadow_strength))
        black = Image.new("RGBA", img.size, (0, 0, 0, 255))
        black.putalpha(shadow_layer)
        img = Image.alpha_composite(img, black)

    text_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    tdraw = ImageDraw.Draw(text_layer)
    for line, x, y in positions():
        _draw_tracked(tdraw, (x, y), line, font, fill + (255,), tracking)
    return Image.alpha_composite(img, text_layer)


def make_rule(width: int, height: int, color: tuple[int, int, int], radius: int = 0) -> Image.Image:
    """A small accent bar/line as an RGBA image."""
    img = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=color + (255,))
    return img
