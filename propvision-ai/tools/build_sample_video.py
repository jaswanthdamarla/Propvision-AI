"""Render sample_data/propvision_sample_demo.mp4 with the production renderer.

Usage:  python tools/build_sample_video.py [theme] [aspect] [resolution]
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.content_engine import generate_content  # noqa: E402
from core.models import PropertyInfo, RenderSettings  # noqa: E402
from core.storyboard import count_photo_scenes  # noqa: E402
from video.ambient import write_ambient_wav  # noqa: E402
from video.renderer import render_video  # noqa: E402


def main() -> None:
    theme = sys.argv[1] if len(sys.argv) > 1 else "Luxury Editorial"
    aspect = sys.argv[2] if len(sys.argv) > 2 else "9:16"
    resolution = sys.argv[3] if len(sys.argv) > 3 else "720p"
    sample = ROOT / "sample_data"
    info = PropertyInfo.from_dict(json.loads((sample / "sample_property.json").read_text(encoding="utf-8")))
    photos = [str(sample / f"demo_visual_{i}.jpg") for i in range(1, 5)]
    duration = 30
    content = generate_content(info, count_photo_scenes(len(photos), duration))
    with tempfile.TemporaryDirectory() as tmp:
        music = write_ambient_wav(Path(tmp) / "ambient.wav", duration + 4)
        settings = RenderSettings(aspect=aspect, resolution=resolution, duration=duration, theme=theme,
                                  music_path=str(music), disclaimer="Demo listing · illustrative synthetic images")
        result = render_video(photos, info, content, settings, sample / "propvision_sample_demo.mp4",
                              progress=lambda f, s: print(f"\r{int(f * 100):3d}% {s[:60]:<60}", end="", flush=True))
    print("\n", result)


if __name__ == "__main__":
    main()
