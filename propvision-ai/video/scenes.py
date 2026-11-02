"""Scene layouts: turn text content into positioned, animated ``TextBlock`` objects."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.models import GeneratedContent, PropertyInfo
from .text_layout import TextBlock, fit_text, make_rule, render_text_block
from .themes import RGB, Theme


@dataclass
class LayoutContext:
    width: int
    height: int
    theme: Theme

    @property
    def vertical(self) -> bool:
        return self.height > self.width

    @property
    def u(self) -> float:
        """Scale unit: 1.0 at 1080 px on the short side."""
        return min(self.width, self.height) / 1080

    @property
    def margin_x(self) -> int:
        return int(self.width * 0.075)

    @property
    def margin_bottom(self) -> int:
        return int(self.height * (0.17 if self.vertical else 0.13))

    @property
    def text_width(self) -> int:
        return self.width - 2 * self.margin_x if self.vertical else int(self.width * 0.62)


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))  # type: ignore[return-value]


def _text_block(ctx: LayoutContext, text: str, font_key: str, size: float, color: RGB, max_width: float,
                max_lines: int, min_size: float, tracking_em: float = 0.0, align: str = "left",
                **kwargs) -> TextBlock:
    font, lines, tracking = fit_text(text, font_key, int(size * ctx.u), int(min_size * ctx.u),
                                     max_width, max_lines, tracking_em)
    image = render_text_block(lines, font, color, tracking=tracking, align=align, **kwargs)
    return TextBlock(image, 0, 0)


def _place_stack(ctx: LayoutContext, items: list[tuple[TextBlock, float]], align: str, bottom: Optional[int] = None,
                 center_y: Optional[float] = None, step_delay: float = 0.16) -> list[TextBlock]:
    """Stack blocks top-to-bottom. ``items`` = [(block, gap_before_in_u)]."""
    if not items:
        return []
    gaps = [int(gap * ctx.u) for _, gap in items]
    total = sum(block.height for block, _ in items) + sum(gaps[1:])
    if center_y is not None:
        y = int(center_y - total / 2)
    else:
        y = (bottom if bottom is not None else ctx.height - ctx.margin_bottom) - total
    placed = []
    for index, (block, _) in enumerate(items):
        if index:
            y += gaps[index]
        block.y = y
        block.x = (ctx.width - block.width) // 2 if align == "center" else ctx.margin_x - _shadow_margin(block)
        block.delay = index * step_delay
        block.rise = int(26 * ctx.u)
        placed.append(block)
        y += block.height
    return placed


def _shadow_margin(block: TextBlock) -> int:
    """Left padding baked into a block image (shadow room) - compensate so text aligns to the margin."""
    alpha_box = block.alpha.getbbox()
    return alpha_box[0] if alpha_box else 0


def build_intro_blocks(ctx: LayoutContext, info: PropertyInfo, content: GeneratedContent) -> list[TextBlock]:
    th, u = ctx.theme, ctx.u
    centered = th.caption_style == "minimal"
    align = "center" if centered else "left"
    max_w = ctx.text_width

    parts = [info.category.upper() if info.category and info.category != "Other" else "",
             info.location.split(",")[0].strip().upper() if info.location else ""]
    label_text = "  ·  ".join(p for p in parts if p)
    items: list[tuple[TextBlock, float]] = []
    if label_text:
        if th.caption_style == "bold":
            label = _text_block(ctx, label_text, th.label_font, 28, (10, 10, 10), max_w - 80 * u, 2, 20,
                                tracking_em=th.label_tracking, shadow=False, card=th.accent + (255,),
                                card_radius=int(6 * u), card_padding=(int(18 * u), int(10 * u)))
        else:
            label = _text_block(ctx, label_text, th.label_font, 30, th.accent, max_w, 2, 20,
                                tracking_em=th.label_tracking, align=align)
        items.append((label, 0))

    title = content.headline.upper() if th.uppercase_titles else content.headline
    title_size = 100 if ctx.vertical else 84
    items.append((_text_block(ctx, title, th.title_font, title_size, th.text, max_w, 4 if ctx.vertical else 3,
                              46, align=align, line_spacing=1.12), 26))
    if th.caption_style in ("editorial", "warm"):
        rule = TextBlock(make_rule(int(90 * u), max(2, int(4 * u)), th.accent, radius=int(2 * u)), 0, 0)
        items.append((rule, 30))
    items.append((_text_block(ctx, content.hook, th.body_font, 50, _mix(th.text, (200, 200, 200), 0.12), max_w, 3, 30,
                              align=align), 26))
    return _place_stack(ctx, items, align)


def build_photo_blocks(ctx: LayoutContext, caption: str, number: int, total: int) -> list[TextBlock]:
    th, u = ctx.theme, ctx.u
    style = th.caption_style
    text = caption.upper() if th.uppercase_titles else caption
    counter = f"{number:02d}  /  {total:02d}"
    max_w = ctx.text_width

    if style == "minimal":
        block = _text_block(ctx, text, th.title_font, 54, th.text, max_w - 110 * u, 3, 30, align="center",
                            shadow=False, card=(12, 14, 20, 175), card_radius=int(34 * u),
                            card_padding=(int(44 * u), int(30 * u)), line_spacing=1.2)
        return _place_stack(ctx, [(block, 0)], "center")

    if style == "warm":
        label = _text_block(ctx, counter, th.label_font, 28, th.accent, max_w, 1, 20, tracking_em=th.label_tracking)
        card = _text_block(ctx, text, th.title_font, 56, (62, 40, 28), max_w - 100 * u, 3, 30, shadow=False,
                           card=(253, 245, 233, 240), card_radius=int(40 * u),
                           card_padding=(int(46 * u), int(32 * u)), line_spacing=1.2)
        return _place_stack(ctx, [(label, 0), (card, 18)], "left")

    if style == "bold":
        label = _text_block(ctx, counter, th.label_font, 28, (10, 10, 10), max_w, 1, 20,
                            tracking_em=th.label_tracking, shadow=False, card=th.accent + (255,),
                            card_radius=int(6 * u), card_padding=(int(18 * u), int(10 * u)))
        cap = _text_block(ctx, text, th.title_font, 68, th.text, max_w - 40 * u, 3, 34, line_spacing=1.1)
        bar = TextBlock(make_rule(int(14 * u), cap.height, th.accent, radius=int(3 * u)), 0, 0)
        placed = _place_stack(ctx, [(label, 0), (cap, 22)], "left")
        cap = placed[1]
        cap.x += int(34 * u)
        bar.x, bar.y = ctx.margin_x, cap.y
        bar.delay, bar.rise = cap.delay, cap.rise
        return [placed[0], bar, cap]

    # editorial (default)
    label = _text_block(ctx, counter, th.label_font, 28, th.accent, max_w, 1, 20, tracking_em=th.label_tracking)
    rule = TextBlock(make_rule(int(84 * u), max(2, int(3 * u)), th.accent, radius=int(2 * u)), 0, 0)
    cap = _text_block(ctx, text, th.title_font, 68, th.text, max_w, 3, 36, line_spacing=1.18)
    return _place_stack(ctx, [(label, 0), (rule, 18), (cap, 22)], "left")


def build_cta_blocks(ctx: LayoutContext, info: PropertyInfo, content: GeneratedContent) -> list[TextBlock]:
    th, u = ctx.theme, ctx.u
    max_w = int(ctx.width * 0.84) if ctx.vertical else int(ctx.width * 0.66)
    items: list[tuple[TextBlock, float]] = []

    label_text = info.display_title.upper() if len(info.display_title) <= 60 else info.display_title
    items.append((_text_block(ctx, label_text, th.label_font, 30, th.accent, max_w, 2, 20,
                              tracking_em=th.label_tracking, align="center"), 0))
    closing = content.closing.upper() if th.uppercase_titles else content.closing
    items.append((_text_block(ctx, closing, th.title_font, 74, th.text, max_w, 4, 38, align="center",
                              line_spacing=1.14), 28))
    if info.price:
        items.append((_text_block(ctx, info.price, th.title_font, 92, th.accent, max_w, 2, 44, align="center"), 34))
    if info.location:
        items.append((_text_block(ctx, info.location, th.body_font, 46, _mix(th.text, (200, 200, 200), 0.1), max_w, 2, 30,
                                  align="center"), 20))
    if info.contact:
        pill = _text_block(ctx, info.contact, th.label_font, 44, th.text, max_w - 120 * u, 2, 28, align="center",
                           shadow=False, card=(8, 10, 16, 150), card_radius=int(44 * u),
                           card_padding=(int(46 * u), int(22 * u)), card_outline=th.accent + (255,),
                           outline_width=max(2, int(3 * u)))
        items.append((pill, 40))
    return _place_stack(ctx, items, "center", center_y=ctx.height * (0.47 if ctx.vertical else 0.5))


def build_disclaimer_block(ctx: LayoutContext, text: str) -> TextBlock:
    block = _text_block(ctx, text, "poppins", 24, (232, 232, 232), ctx.width * 0.86, 2, 16, align="center",
                        line_spacing=1.15)
    block.x = (ctx.width - block.width) // 2
    block.y = int(ctx.height - block.height - ctx.height * (0.045 if ctx.vertical else 0.035))
    block.delay = 0.1
    block.duration = 0.5
    block.rise = 0
    return block
