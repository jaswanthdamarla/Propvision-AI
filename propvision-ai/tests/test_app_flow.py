"""Headless UI tests with Streamlit's AppTest (no browser needed)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def new_app():
    return AppTest.from_file(APP, default_timeout=120).run()


def click(at, label):
    next(b for b in at.button if b.label == label).click()
    return at.run()


def test_landing_page_loads():
    at = new_app()
    assert not at.exception
    labels = [b.label for b in at.button]
    assert any("Create Property Video" in l for l in labels)


def test_property_form_validation_blocks_empty_listing():
    at = new_app()
    click(at, "Create Property Video  →")
    assert at.session_state.step == 1
    assert any("title or a location" in e.value for e in at.error)
    cont = next(b for b in at.button if b.label.startswith("Continue"))
    assert cont.disabled
    at.text_input(key="p_title").set_value("My Villa").run()
    assert not any("title or a location" in e.value for e in at.error)
    assert not next(b for b in at.button if b.label.startswith("Continue")).disabled


def test_full_flow_with_sample_renders_video():
    at = new_app()
    click(at, "Try with sample listing")
    assert at.session_state.p_title == "Skyline Residency" and len(at.session_state.photos) == 4
    click(at, "Continue →")                       # -> photos
    assert at.session_state.step == 2
    click(at, "Continue →")                       # -> style
    at.radio(key="s_duration").set_value(20)
    at.run()
    click(at, "Continue →")                       # -> content
    assert at.session_state.step == 4
    assert at.session_state.content.engine == "rule-based"
    assert at.text_input(key="ed_headline").value.startswith("Discover")
    at.text_input(key="ed_cap_0").set_value("My edited caption.").run()
    click(at, "Continue to render →")
    assert at.session_state.step == 5
    click(at, "🎬 Generate Video")
    assert not at.exception
    result = at.session_state.result
    assert result is not None, [e.value for e in at.error]
    assert Path(result.path).exists() and result.size_bytes > 20_000
    assert abs(result.duration - 20) < 0.3
    assert len(at.session_state.video_bytes) == result.size_bytes
    Path(result.path).unlink()


def test_too_few_photos_blocks_continue():
    at = new_app()
    click(at, "Try with sample listing")
    click(at, "Continue →")
    at.session_state.photos = at.session_state.photos[:2]
    at.run()
    assert any("at least 4" in e.value or "2 more" in e.value for e in list(at.error) + list(at.info))
    assert next(b for b in at.button if b.label.startswith("Continue")).disabled
