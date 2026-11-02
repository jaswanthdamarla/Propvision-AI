"""Video renderer: Ken Burns photo scenes, text overlays, transitions and FFmpeg H.264 encoding.

Frames are drawn with Pillow/NumPy and streamed straight into FFmpeg (libx264, optional AAC audio).
Nothing is a pre-baked slideshow - every frame is composed from the photo crop, gradient, text
animation and transition state at that instant.
"""
from __future__ import annotations

import math
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from core import config
from core.models import GeneratedContent, PropertyInfo, RenderResult, RenderSettings, SceneSpec
from core.storyboard import photos_used, plan_scenes
from core.validator import probe_media
from .scenes import (LayoutContext, build_cta_blocks, build_disclaimer_block, build_intro_blocks,
                     build_photo_blocks)
from .text_layout import TextBlock
from .themes import Theme, get_theme

ProgressCallback = Callable[[float, str], None]

PAD = 1.25                  # photo is prepared 25 % larger than the frame so crops stay sharp
BLUR_FILL_MISMATCH = 2.4    # aspect mismatch above which the photo is shown whole on a blurred backdrop
MAX_SOURCE_SIDE = 4096


class RenderError(Exception):
    """A rendering failure with a message that is safe to show to the user."""


# --------------------------------------------------------------------------
# Easing helpers
# --------------------------------------------------------------------------
def smoothstep(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def ease_out_cubic(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def camera_ease(x: float) -> float:
    """Gentle ease-in-out that stays mostly linear so motion never feels stalled."""
    x = min(1.0, max(0.0, x))
    return 0.4 * x + 0.6 * smoothstep(x)


# --------------------------------------------------------------------------
# Photo preparation
# --------------------------------------------------------------------------
def load_photo(path: str | Path) -> Image.Image:
    """Open a photo, honour EXIF rotation, flatten transparency and bound its size."""
    try:
        with Image.open(path) as img:
            if img.format == "JPEG":
                img.draft("RGB", (MAX_SOURCE_SIDE, MAX_SOURCE_SIDE))
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                rgba = img.convert("RGBA")
                backdrop = Image.new("RGBA", rgba.size, (28, 28, 32, 255))
                img = Image.alpha_composite(backdrop, rgba).convert("RGB")
            else:
                img = img.convert("RGB")
            if max(img.size) > MAX_SOURCE_SIDE:
                img.thumbnail((MAX_SOURCE_SIDE, MAX_SOURCE_SIDE), Image.LANCZOS)
            return img.copy()
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise RenderError(f"Could not read photo '{Path(path).name}': {exc}") from exc


@dataclass
class PreparedPhoto:
    image: Image.Image
    box_w: float
    box_h: float
    blur_mode: bool

    @property
    def slack_x(self) -> float:
        return 1 - self.box_w / self.image.width

    @property
    def slack_y(self) -> float:
        return 1 - self.box_h / self.image.height


def _grade(img: Image.Image, theme: Theme) -> Image.Image:
    if theme.contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(theme.contrast)
    if theme.saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(theme.saturation)
    if theme.brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(theme.brightness)
    if theme.warmth:
        img = Image.blend(img, Image.new("RGB", img.size, (255, 206, 150)), theme.warmth)
    return img


def prepare_photo(img: Image.Image, width: int, height: int, theme: Theme) -> PreparedPhoto:
    target_ar = width / height
    iw, ih = img.size
    mismatch = max((iw / ih) / target_ar, target_ar / (iw / ih))
    cw, ch = round(width * PAD), round(height * PAD)

    if mismatch > BLUR_FILL_MISMATCH:
        backdrop = ImageOps.fit(img, (cw, ch), Image.BILINEAR)
        backdrop = backdrop.filter(ImageFilter.GaussianBlur(min(cw, ch) * 0.035))
        backdrop = Image.blend(backdrop, Image.new("RGB", backdrop.size, (0, 0, 0)), 0.45)
        scale = min(cw * 0.94 / iw, ch * 0.94 / ih)
        fg = img.resize((max(1, round(iw * scale)), max(1, round(ih * scale))), Image.LANCZOS, reducing_gap=2.0)
        fg = _grade(fg, theme)
        pos = ((cw - fg.width) // 2, (ch - fg.height) // 2)
        shadow = Image.new("L", backdrop.size, 0)
        shadow.paste(255, (pos[0], pos[1] + int(ch * 0.01), pos[0] + fg.width, pos[1] + fg.height + int(ch * 0.01)))
        shadow = shadow.filter(ImageFilter.GaussianBlur(min(cw, ch) * 0.02)).point(lambda v: int(v * 0.6))
        backdrop.paste(Image.new("RGB", backdrop.size, (0, 0, 0)), (0, 0), shadow)
        backdrop.paste(fg, pos)
        return PreparedPhoto(backdrop, float(cw), float(ch), True)

    scale = max(cw / iw, ch / ih)
    scaled = img.resize((max(1, round(iw * scale)), max(1, round(ih * scale))), Image.LANCZOS, reducing_gap=2.0)
    scaled = _grade(scaled, theme)
    sw, sh = scaled.size
    if sw / sh > target_ar:
        box_h, box_w = float(sh), sh * target_ar
    else:
        box_w, box_h = float(sw), sw / target_ar
    return PreparedPhoto(scaled, box_w, box_h, False)


def make_backdrop(prepared: PreparedPhoto, darkness: float = 0.5) -> PreparedPhoto:
    """Darker, slightly soft copy of a prepared photo for the closing scene."""
    softened = prepared.image.filter(ImageFilter.GaussianBlur(max(1.5, prepared.image.width * 0.0025)))
    dimmed = Image.blend(softened, Image.new("RGB", softened.size, (0, 0, 0)), darkness)
    return PreparedPhoto(dimmed, prepared.box_w, prepared.box_h, prepared.blur_mode)


# --------------------------------------------------------------------------
# Ken Burns motion
# --------------------------------------------------------------------------
@dataclass
class Motion:
    z0: float
    z1: float
    fx0: float = 0.5
    fx1: float = 0.5
    fy0: float = 0.5
    fy1: float = 0.5


def choose_motion(kind: str, index: int, prepared: PreparedPhoto, theme: Theme, reuse: bool) -> Motion:
    intensity = theme.zoom_intensity
    if kind == "intro":
        return Motion(1.0, 1.0 + intensity, 0.45, 0.55, 0.55, 0.45)
    if kind == "cta":
        return Motion(1.0 + intensity * 0.5, 1.0)
    if prepared.blur_mode:
        return Motion(1.0, 1.0 + intensity * 0.7) if index % 2 == 0 else Motion(1.0 + intensity * 0.7, 1.0)
    if reuse:   # a different "detail" view of a photo that was already shown
        return Motion(1.0 + intensity * 1.7, 1.0 + intensity * 2.0, 0.2, 0.75, 0.3, 0.65)

    sx, sy = prepared.slack_x, prepared.slack_y
    flip = index % 2 == 1
    if sx >= 0.14 and sx >= sy * 1.2:      # wide photo -> pan left/right
        a, b = (0.12, 0.88) if not flip else (0.88, 0.12)
        return Motion(1.02, 1.0 + intensity * 0.6, a, b, 0.5, 0.5)
    if sy >= 0.14 and sy > sx * 1.2:       # tall photo -> pan up/down
        a, b = (0.85, 0.2) if not flip else (0.2, 0.85)
        return Motion(1.02, 1.0 + intensity * 0.6, 0.5, 0.5, a, b)
    patterns = [
        Motion(1.0, 1.0 + intensity, 0.5, 0.5, 0.5, 0.5),                    # push in
        Motion(1.0 + intensity, 1.0, 0.5, 0.5, 0.5, 0.5),                    # pull out
        Motion(1.0, 1.0 + intensity, 0.35, 0.7, 0.6, 0.35),                  # drift up-right
        Motion(1.0 + intensity * 0.4, 1.0 + intensity * 1.2, 0.7, 0.3, 0.4, 0.65),   # drift down-left
    ]
    return patterns[index % len(patterns)]


def crop_box(prepared: PreparedPhoto, motion: Motion, p: float) -> tuple[float, float, float, float]:
    e = camera_ease(p)
    zoom = motion.z0 + (motion.z1 - motion.z0) * e
    fx = motion.fx0 + (motion.fx1 - motion.fx0) * e
    fy = motion.fy0 + (motion.fy1 - motion.fy0) * e
    bw, bh = prepared.box_w / zoom, prepared.box_h / zoom
    sw, sh = prepared.image.size
    x0 = fx * (sw - bw)
    y0 = fy * (sh - bh)
    x0 = min(max(0.0, x0), sw - bw)
    y0 = min(max(0.0, y0), sh - bh)
    return (x0, y0, x0 + bw, y0 + bh)


# --------------------------------------------------------------------------
# Gradient overlays
# --------------------------------------------------------------------------
_MASK_CACHE: dict[tuple, Image.Image] = {}


def gradient_mask(width: int, height: int, start: float, max_alpha: float, global_dim: float,
                  top_alpha: float = 0.0) -> Image.Image:
    key = (width, height, round(start, 3), round(max_alpha, 3), round(global_dim, 3), round(top_alpha, 3))
    cached = _MASK_CACHE.get(key)
    if cached is not None:
        return cached
    y = np.linspace(0.0, 1.0, height)
    ramp = np.clip((y - start) / max(1e-6, 1 - start), 0, 1)
    ramp = ramp * ramp * (3 - 2 * ramp)
    alpha = global_dim + (max_alpha - global_dim) * ramp ** 0.85
    if top_alpha:
        top = np.clip(1 - y / 0.22, 0, 1) ** 2 * top_alpha
        alpha = np.maximum(alpha, top)
    rng = np.random.default_rng(3)
    noise = rng.uniform(-0.5, 0.5, (height, width)).astype(np.float32)   # dither against banding
    arr = np.clip(alpha[:, None] * 255 + noise, 0, 255).astype(np.uint8)
    mask = Image.fromarray(arr, "L")
    if len(_MASK_CACHE) > 12:
        _MASK_CACHE.clear()
    _MASK_CACHE[key] = mask
    return mask


# --------------------------------------------------------------------------
# A single scene
# --------------------------------------------------------------------------
@dataclass
class SceneRuntime:
    spec: SceneSpec
    start: float
    visible: float                 # seconds the scene stays on screen (incl. outgoing overlap)
    prepared: PreparedPhoto
    motion: Motion
    mask: Image.Image
    tint: Image.Image
    blocks: list[TextBlock]
    text_start: float
    transition_in: float           # seconds of incoming transition (0 for the first scene)

    def frame(self, local_t: float, size: tuple[int, int]) -> Image.Image:
        width, height = size
        progress = local_t / self.visible if self.visible > 0 else 0.0
        box = crop_box(self.prepared, self.motion, progress)
        frame = self.prepared.image.resize((width, height), Image.BILINEAR, box=box)
        frame.paste(self.tint, (0, 0), self.mask)

        text_t = local_t - self.text_start
        if text_t > 0:
            for block in self.blocks:
                amount = ease_out_cubic((text_t - block.delay) / block.duration)
                if amount <= 0:
                    continue
                mask = block.alpha
                if amount < 0.999:
                    lut = [int(i * amount + 0.5) for i in range(256)]
                    mask = mask.point(lut)
                frame.paste(block.rgb, (block.x, int(block.y + (1 - amount) * block.rise)), mask)
        return frame


def _transition(old: Image.Image, new: Image.Image, p: float, kind: str, vertical: bool) -> Image.Image:
    e = smoothstep(p)
    if kind == "slide":
        width, height = new.size
        canvas = old.copy()
        if vertical:
            canvas = Image.new("RGB", old.size)
            canvas.paste(old, (0, -int(height * 0.25 * e)))
            canvas.paste(new, (0, int(height * (1 - e))))
        else:
            canvas = Image.new("RGB", old.size)
            canvas.paste(old, (-int(width * 0.25 * e), 0))
            canvas.paste(new, (int(width * (1 - e)), 0))
        return canvas
    return Image.blend(old, new, e)


# --------------------------------------------------------------------------
# Composer: whole timeline
# --------------------------------------------------------------------------
class VideoComposer:
    """Builds every scene once and can render any frame of the final timeline."""

    def __init__(self, photo_paths: list[str], info: PropertyInfo, content: GeneratedContent,
                 settings: RenderSettings, progress: Optional[ProgressCallback] = None) -> None:
        if not photo_paths:
            raise RenderError("No photographs were provided.")
        if settings.duration < 6:
            raise RenderError("The video duration is too short.")
        if (settings.aspect, settings.resolution) not in config.VIDEO_SIZES:
            raise RenderError(f"Unsupported aspect ratio / resolution: {settings.aspect} {settings.resolution}.")

        self.settings = settings
        self.theme = get_theme(settings.theme)
        self.width, self.height = settings.size
        self.fps = settings.fps
        self.progress = progress or (lambda fraction, stage: None)
        self.scene_specs = plan_scenes(len(photo_paths), settings.duration)
        self.photos_used = photos_used(self.scene_specs)
        self.ctx = LayoutContext(self.width, self.height, self.theme)

        self.prepared: dict[int, PreparedPhoto] = {}
        needed = sorted({s.photo_index for s in self.scene_specs})
        for count, index in enumerate(needed, start=1):
            self.progress(0.05 * count / len(needed), f"Preparing photographs ({count}/{len(needed)})")
            self.prepared[index] = prepare_photo(load_photo(photo_paths[index]), self.width, self.height, self.theme)

        self.scenes = self._build_scenes(info, content)
        self.total_seconds = sum(s.duration for s in self.scene_specs)
        self.total_frames = int(round(self.total_seconds * self.fps))

    # -- construction ------------------------------------------------------
    def _build_scenes(self, info: PropertyInfo, content: GeneratedContent) -> list[SceneRuntime]:
        theme, ctx = self.theme, self.ctx
        photo_total = sum(1 for s in self.scene_specs if s.kind == "photo")
        captions = list(content.scene_captions) + [""] * photo_total
        scenes: list[SceneRuntime] = []
        start = 0.0
        photo_number = 0
        disclaimer = build_disclaimer_block(ctx, self.settings.disclaimer) if self.settings.disclaimer else None
        for position, spec in enumerate(self.scene_specs):
            is_last = position == len(self.scene_specs) - 1
            transition_in = 0.0 if position == 0 else theme.transition_seconds
            next_overlap = 0.0 if is_last else theme.transition_seconds
            visible = spec.duration + next_overlap

            prepared = self.prepared[spec.photo_index]
            if spec.kind == "cta":
                prepared = make_backdrop(prepared, 0.52)
                blocks = build_cta_blocks(ctx, info, content)
                mask = gradient_mask(self.width, self.height, 0.0, 0.5, 0.42, 0.0)
            elif spec.kind == "intro":
                blocks = build_intro_blocks(ctx, info, content)
                mask = gradient_mask(self.width, self.height, 0.28 if ctx.vertical else 0.2,
                                     theme.gradient_strength + 0.04, 0.2, 0.35)
            else:
                photo_number += 1
                caption = captions[photo_number - 1] or ""
                blocks = build_photo_blocks(ctx, caption, photo_number, photo_total) if caption else []
                mask = gradient_mask(self.width, self.height, 0.46 if ctx.vertical else 0.38,
                                     theme.gradient_strength, 0.05, 0.25)
            if disclaimer is not None:
                blocks = blocks + [_clone_block(disclaimer)]

            motion = choose_motion(spec.kind, max(photo_number - 1, 0), prepared, theme, spec.reuse)
            scenes.append(SceneRuntime(
                spec=spec, start=start, visible=visible, prepared=prepared, motion=motion, mask=mask,
                tint=Image.new("RGB", (self.width, self.height), theme.tint, ),
                blocks=blocks, text_start=0.25 if position == 0 else transition_in * 0.55,
                transition_in=transition_in,
            ))
            start += spec.duration
        return scenes

    # -- per-frame ---------------------------------------------------------
    def _scene_at(self, t: float) -> int:
        index = 0
        for i, scene in enumerate(self.scenes):
            if scene.start <= t + 1e-9:
                index = i
        return index

    def render_frame(self, frame_index: int) -> Image.Image:
        t = frame_index / self.fps
        size = (self.width, self.height)
        i = self._scene_at(t)
        scene = self.scenes[i]
        current = scene.frame(t - scene.start, size)
        if i > 0 and scene.transition_in > 0:
            elapsed = t - scene.start
            if elapsed < scene.transition_in:
                previous = self.scenes[i - 1]
                old = previous.frame(t - previous.start, size)
                return _transition(old, current, elapsed / scene.transition_in,
                                   self.theme.transition, self.ctx.vertical)
        return current

    def scene_label_at(self, frame_index: int) -> tuple[int, str]:
        i = self._scene_at(frame_index / self.fps)
        return i, self.scenes[i].spec.label


def _clone_block(block: TextBlock) -> TextBlock:
    clone = TextBlock(block.image, block.x, block.y, block.delay, block.duration, block.rise)
    return clone


# --------------------------------------------------------------------------
# FFmpeg encoding
# --------------------------------------------------------------------------
def _ffmpeg_command(ffmpeg: str, composer: VideoComposer, output: Path, music: Optional[str]) -> list[str]:
    fps = composer.fps
    duration = composer.total_seconds
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{composer.width}x{composer.height}",
           "-framerate", str(fps), "-i", "-"]
    if music:
        cmd += ["-stream_loop", "-1", "-i", music]
    cmd += ["-map", "0:v:0"]
    if music:
        cmd += ["-map", "1:a:0"]
    cmd += ["-vf", "scale=out_color_matrix=bt709:out_range=tv",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-r", str(fps), "-g", str(fps * 2),
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-movflags", "+faststart"]
    if music:
        fade_out_start = max(0.0, duration - 2.0)
        cmd += ["-af", f"afade=t=in:st=0:d=1.5,afade=t=out:st={fade_out_start:.2f}:d=2,volume=0.9",
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2"]
    cmd += ["-t", f"{duration:.3f}", "-f", "mp4", str(output)]
    return cmd


def _encode(composer: VideoComposer, output: Path, music: Optional[str], progress: ProgressCallback) -> None:
    ffmpeg = config.find_ffmpeg()
    cmd = _ffmpeg_command(ffmpeg, composer, output, music)
    with tempfile.TemporaryFile() as err_file:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=err_file)
        try:
            total = composer.total_frames
            last_scene = -1
            for frame_index in range(total):
                scene_number, label = composer.scene_label_at(frame_index)
                if scene_number != last_scene:
                    last_scene = scene_number
                stage = f"Rendering scene {scene_number + 1}/{len(composer.scenes)} - {label}"
                if frame_index % 5 == 0:
                    progress(0.05 + 0.92 * frame_index / total, stage)
                frame = composer.render_frame(frame_index)
                proc.stdin.write(frame.tobytes())          # type: ignore[union-attr]
            progress(0.97, "Finalising MP4")
            proc.stdin.close()                             # type: ignore[union-attr]
            return_code = proc.wait(timeout=300)
        except BrokenPipeError:
            proc.wait(timeout=30)
            return_code = proc.returncode or 1
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        if return_code != 0:
            err_file.seek(0)
            tail = err_file.read().decode("utf-8", "replace").strip().splitlines()[-4:]
            raise RenderError("FFmpeg failed while encoding: " + " | ".join(tail))


def render_video(photo_paths: list[str], info: PropertyInfo, content: GeneratedContent,
                 settings: RenderSettings, output_path: str | Path,
                 progress: Optional[ProgressCallback] = None) -> RenderResult:
    """Render the final MP4. Raises ``RenderError`` with a readable message on failure."""
    progress = progress or (lambda fraction, stage: None)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    try:
        composer = VideoComposer(photo_paths, info, content, settings, progress)
    except RenderError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RenderError(f"Could not prepare the video: {exc}") from exc

    if composer.photos_used < len(photo_paths):
        warnings.append(
            f"With a {settings.duration}-second video, {composer.photos_used} of your {len(photo_paths)} "
            "photographs fit comfortably. Choose a longer duration to show every photo."
        )

    music = settings.music_path
    if music:
        try:
            if not Path(music).exists() or not probe_media(music)["has_audio"]:
                warnings.append("The background music file has no usable audio, so the video was rendered without music.")
                music = None
        except Exception:  # noqa: BLE001
            warnings.append("The background music could not be read, so the video was rendered without music.")
            music = None

    partial = output.with_name(output.stem + ".partial.mp4")
    attempts = [music, None] if music else [None]
    last_error: Optional[Exception] = None
    for attempt, music_file in enumerate(attempts):
        try:
            _encode(composer, partial, music_file, progress)
            if attempt == 1:
                warnings.append("Encoding with the music track failed, so the video was rendered without music.")
            last_error = None
            has_audio = music_file is not None
            break
        except RenderError as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            partial.unlink(missing_ok=True)
            raise RenderError(f"Rendering failed: {exc}") from exc
    if last_error is not None:
        raise RenderError(str(last_error))

    try:
        info_probe = probe_media(partial)
        expected = composer.total_frames / composer.fps
        if (not partial.exists() or partial.stat().st_size < 10_000 or not info_probe["has_video"]
                or info_probe["duration"] is None or abs(info_probe["duration"] - expected) > 0.5):
            raise RenderError("The rendered file failed verification (wrong duration or empty output).")
        partial.replace(output)
    except RenderError:
        partial.unlink(missing_ok=True)
        raise
    progress(1.0, "Done")
    return RenderResult(
        path=str(output), duration=info_probe["duration"] or expected, width=composer.width,
        height=composer.height, fps=composer.fps, size_bytes=output.stat().st_size,
        scenes=len(composer.scenes), photos_used=composer.photos_used, has_audio=has_audio, warnings=warnings,
    )
