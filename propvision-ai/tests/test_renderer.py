import subprocess

import numpy as np
import pytest
from PIL import Image

from core import config
from core.content_engine import generate_content
from core.models import PropertyInfo, RenderSettings
from core.storyboard import count_photo_scenes
from core.validator import probe_media
from video.renderer import RenderError, VideoComposer, render_video

INFO = PropertyInfo.from_dict(dict(title="Test Heights", location="Hyderabad", price="₹1 Cr", category="Villa",
                                   bedrooms=4, amenities=["Garden", "Pool", "Garage"], contact="+91-00000-00000"))


@pytest.fixture
def photos(tmp_path):
    """Photos with different sizes/orientations incl. portrait, panorama, PNG with alpha, WEBP, EXIF-less."""
    specs = [((1600, 1200), "JPEG", ".jpg"), ((900, 1600), "JPEG", ".jpg"), ((3000, 1000), "PNG", ".png"),
             ((800, 800), "WEBP", ".webp"), ((2400, 1600), "JPEG", ".jpg")]
    paths = []
    rng = np.random.default_rng(0)
    for i, (size, fmt, ext) in enumerate(specs):
        arr = (rng.random((size[1] // 20, size[0] // 20, 3)) * 255).astype("uint8")
        img = Image.fromarray(arr).resize(size, Image.BICUBIC)
        if fmt == "PNG":
            img = img.convert("RGBA")
        p = tmp_path / f"p{i}{ext}"
        img.save(p, fmt)
        paths.append(str(p))
    return paths


def _content(n=5, duration=20):
    return generate_content(INFO, count_photo_scenes(n, duration))


@pytest.mark.parametrize("aspect,res,size", [("9:16", "720p", (720, 1280)), ("16:9", "720p", (1280, 720))])
def test_full_render_mixed_photos(photos, tmp_path, aspect, res, size):
    settings = RenderSettings(aspect=aspect, resolution=res, duration=20, theme="Bold Contemporary")
    out = tmp_path / "o.mp4"
    stages = []
    result = render_video(photos, INFO, _content(5), settings, out, progress=lambda f, s: stages.append((f, s)))
    assert out.exists() and result.size_bytes > 20_000
    assert (result.width, result.height) == size
    assert abs(result.duration - 20) < 0.2
    info = probe_media(out)
    assert info["has_video"] and not info["has_audio"]
    assert stages[0][0] <= 0.06 and stages[-1][0] == 1.0
    assert any("Rendering scene" in s for _, s in stages)
    assert not list(tmp_path.glob("*.partial.mp4"))


def test_h264_codec(photos, tmp_path):
    out = tmp_path / "o.mp4"
    render_video(photos, INFO, _content(5), RenderSettings(duration=20), out)
    probe = subprocess.run([config.find_ffmpeg(), "-hide_banner", "-i", str(out)], capture_output=True, text=True).stderr
    assert "h264" in probe and "yuv420p" in probe and "30 fps" in probe


def test_no_black_frames_and_motion(photos):
    composer = VideoComposer(photos, INFO, _content(5), RenderSettings(duration=20))
    means = [np.asarray(composer.render_frame(f)).mean() for f in range(0, composer.total_frames, 15)]
    assert min(means) > 12
    # Ken Burns: two frames inside one scene differ
    a = np.asarray(composer.render_frame(150)).astype(int)
    b = np.asarray(composer.render_frame(165)).astype(int)
    assert np.abs(a - b).mean() > 0.05


def test_every_theme_renders_frames(photos):
    for theme in ("Luxury Editorial", "Modern Minimal", "Warm & Welcoming", "Bold Contemporary"):
        composer = VideoComposer(photos, INFO, _content(5), RenderSettings(duration=20, theme=theme))
        frame = composer.render_frame(60)
        assert frame.size == (720, 1280)


def test_music_is_muxed(photos, tmp_path):
    from video.ambient import write_ambient_wav
    music = write_ambient_wav(tmp_path / "m.wav", 8)          # shorter than video -> must loop
    out = tmp_path / "o.mp4"
    result = render_video(photos, INFO, _content(5), RenderSettings(duration=20, music_path=str(music)), out)
    assert result.has_audio and probe_media(out)["has_audio"]
    assert abs(probe_media(out)["duration"] - 20) < 0.3


def test_invalid_music_falls_back_to_silent(photos, tmp_path):
    bad = tmp_path / "bad.mp3"
    bad.write_bytes(b"not audio" * 100)
    result = render_video(photos, INFO, _content(5), RenderSettings(duration=20, music_path=str(bad)), tmp_path / "o.mp4")
    assert not result.has_audio and any("music" in w.lower() for w in result.warnings)


def test_missing_music_file_falls_back(photos, tmp_path):
    result = render_video(photos, INFO, _content(5), RenderSettings(duration=20, music_path=str(tmp_path / "nope.mp3")), tmp_path / "o.mp4")
    assert not result.has_audio and result.warnings


def test_corrupt_photo_raises_readable_error_and_leaves_no_output(photos, tmp_path):
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(b"garbage")
    out = tmp_path / "o.mp4"
    with pytest.raises(RenderError) as exc:
        render_video(photos[:3] + [str(broken)], INFO, _content(4), RenderSettings(duration=20), out)
    assert "broken.jpg" in str(exc.value)
    assert not out.exists()


def test_no_photos_error(tmp_path):
    with pytest.raises(RenderError):
        render_video([], INFO, _content(4), RenderSettings(), tmp_path / "o.mp4")


def test_missing_optional_everything_still_renders(photos, tmp_path):
    bare = PropertyInfo.from_dict({"title": "Bare Listing"})
    content = generate_content(bare, count_photo_scenes(5, 20))
    result = render_video(photos, bare, content, RenderSettings(duration=20), tmp_path / "o.mp4")
    assert result.size_bytes > 0


def test_very_large_photo_is_handled(tmp_path, photos):
    big = tmp_path / "big.jpg"
    Image.new("RGB", (7000, 5000), (90, 140, 90)).save(big, quality=60)
    result = render_video(photos[:3] + [str(big)], INFO, _content(4), RenderSettings(duration=20), tmp_path / "o.mp4")
    assert result.size_bytes > 0


def test_warns_when_photos_do_not_all_fit(tmp_path, photos):
    more = photos + photos[:3]        # 8 photos in 20 s
    result = render_video(more, INFO, generate_content(INFO, count_photo_scenes(8, 20)), RenderSettings(duration=20), tmp_path / "o.mp4")
    assert result.photos_used < 8 and any("photographs fit" in w for w in result.warnings)


def test_long_text_does_not_crash(photos):
    nasty = PropertyInfo.from_dict(dict(title="Supercalifragilisticexpialidocious " * 2, location="L" * 70, price="₹" + "9" * 30,
                                        amenities=["A" * 55] * 8, contact="x" * 70, category="Apartment"))
    composer = VideoComposer(photos, nasty, generate_content(nasty, count_photo_scenes(5, 20)), RenderSettings(duration=20))
    for f in (30, 150, 560):
        composer.render_frame(f)
