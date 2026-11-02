import io
import wave

import pytest
from PIL import Image

from core import config
from core.models import PropertyInfo
from core.validator import check_image, validate_images, validate_music, validate_property


def good_info(**kw):
    base = dict(title="Skyline Residency", location="Gachibowli, Hyderabad", price="₹85 Lakhs",
                category="Apartment", bedrooms=3, bathrooms=2, contact="+91-98765-43210")
    base.update(kw)
    return PropertyInfo.from_dict(base)


# ---- property ------------------------------------------------------------
def test_complete_property_is_valid_without_warnings():
    result = validate_property(good_info())
    assert result.ok and not result.warnings


def test_missing_title_is_a_warning_when_location_present():
    result = validate_property(good_info(title=""))
    assert result.ok and any("title" in w.lower() for w in result.warnings)


def test_missing_title_and_location_is_an_error():
    result = validate_property(good_info(title="", location=""))
    assert not result.ok


@pytest.mark.parametrize("field,word", [("location", "location"), ("price", "price"), ("contact", "contact")])
def test_missing_optional_fields_warn_but_pass(field, word):
    result = validate_property(good_info(**{field: ""}))
    assert result.ok
    assert any(word in w.lower() for w in result.warnings)


def test_all_optional_fields_missing_still_valid_with_title_only():
    result = validate_property(PropertyInfo.from_dict({"title": "Green Villa"}))
    assert result.ok


def test_overlong_title_rejected():
    assert not validate_property(good_info(title="x" * 200)).ok


def test_bad_contact_gets_warning():
    result = validate_property(good_info(contact="call me"))
    assert result.ok and any("contact" in w.lower() for w in result.warnings)


def test_bad_email_gets_warning():
    assert any("email" in w.lower() for w in validate_property(good_info(contact="a@b")).warnings)


# ---- images --------------------------------------------------------------
def test_valid_jpeg_png_webp(img_bytes):
    for fmt, name in (("JPEG", "a.jpg"), ("PNG", "a.png"), ("WEBP", "a.webp")):
        assert check_image(name, img_bytes(fmt=fmt)).ok, fmt


def test_unsupported_extension_rejected(img_bytes):
    check = check_image("photo.gif", img_bytes(fmt="GIF"))
    assert not check.ok and "unsupported" in check.message.lower()


def test_fake_image_rejected():
    check = check_image("fake.jpg", b"this is not an image at all")
    assert not check.ok and "could not be read" in check.message


def test_wrong_content_type_rejected(img_bytes):
    # a real BMP renamed to .jpg
    check = check_image("bmp.jpg", img_bytes(fmt="BMP"))
    assert not check.ok


def test_empty_file_rejected():
    assert not check_image("e.jpg", b"").ok


def test_tiny_image_rejected(img_bytes):
    assert not check_image("t.jpg", img_bytes(size=(100, 100))).ok


def test_low_resolution_warns(img_bytes):
    check = check_image("lo.jpg", img_bytes(size=(600, 450)))
    assert check.ok and check.warning


def test_very_large_image_rejected(monkeypatch, img_bytes):
    monkeypatch.setattr(config, "MAX_IMAGE_PIXELS", 1_000_000)
    check = check_image("big.jpg", img_bytes(size=(1600, 1200)))
    assert not check.ok and "too many pixels" in check.message


def test_large_but_allowed_image_accepted(img_bytes):
    assert check_image("ok.jpg", img_bytes(size=(6000, 4000))).ok


def test_oversized_file_rejected(monkeypatch, img_bytes):
    monkeypatch.setattr(config, "MAX_IMAGE_BYTES", 1000)
    assert not check_image("x.jpg", img_bytes()).ok


@pytest.mark.parametrize("count,ok", [(0, False), (3, False), (4, True), (8, True), (9, False), (12, False)])
def test_image_count_limits(img_bytes, count, ok):
    items = [(f"p{i}.jpg", img_bytes()) for i in range(count)]
    result, _ = validate_images(items)
    assert result.ok is ok
    if not ok:
        assert result.errors


def test_error_messages_mention_how_many(img_bytes):
    result, _ = validate_images([(f"p{i}.jpg", img_bytes()) for i in range(2)])
    assert "2 more" in result.errors[0]
    result, _ = validate_images([(f"p{i}.jpg", img_bytes()) for i in range(10)])
    assert "maximum is 8" in result.errors[0]


def test_mixed_set_reports_each_bad_file(img_bytes):
    items = [(f"p{i}.jpg", img_bytes()) for i in range(4)] + [("bad.gif", b"GIF89a")]
    result, checks = validate_images(items)
    assert not result.ok and sum(1 for c in checks if not c.ok) == 1


# ---- music ---------------------------------------------------------------
def _wav_bytes(seconds=1.0):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00\x01" * int(8000 * seconds))
    return buffer.getvalue()


def test_valid_wav_accepted():
    assert validate_music("a.wav", data=_wav_bytes(4)).ok


def test_invalid_music_content_rejected():
    result = validate_music("a.mp3", data=b"definitely not audio" * 50)
    assert not result.ok


def test_unsupported_music_extension_rejected():
    assert not validate_music("a.exe", data=b"123").ok


def test_empty_music_rejected():
    assert not validate_music("a.mp3", data=b"").ok
