"""PropVision AI - Streamlit application.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import hashlib
import json
import traceback
import uuid
from dataclasses import replace
from pathlib import Path

import streamlit as st

from core import config
from core.content_engine import generate_content
from core.models import GeneratedContent, PropertyInfo, RenderSettings, parse_amenities
from core.pipeline import (cleanup_old_uploads, output_path_for, prepare_music, save_photos,
                           thumbnail_bytes)
from core.storyboard import count_photo_scenes, photos_used, plan_scenes
from core.validator import check_image, validate_images, validate_music, validate_property
from ui import components as ui
from ui.styles import CSS
from video.renderer import RenderError, render_video
from video.themes import THEMES

SAMPLE_JSON = config.SAMPLE_DIR / "sample_property.json"
SAMPLE_VIDEO = config.SAMPLE_DIR / "propvision_sample_demo.mp4"
SAMPLE_DISCLAIMER = "Demo listing · illustrative synthetic images"

THEME_BLURBS = {
    "Luxury Editorial": "Serif headlines, gold accents, slow cross-dissolves.",
    "Modern Minimal": "Clean sans-serif, frosted caption cards, calm motion.",
    "Warm & Welcoming": "Friendly cream caption cards, warm colour grade.",
    "Bold Contemporary": "Uppercase impact type, neon accent, quick slide transitions.",
}
MUSIC_MODES = {"No music": "none", "Built-in ambient (synthesised)": "ambient", "Upload my own": "upload"}
STEP_HOME, STEP_PROPERTY, STEP_PHOTOS, STEP_STYLE, STEP_CONTENT, STEP_EXPORT = range(6)

st.set_page_config(page_title="PropVision AI", page_icon="🏙️", layout="wide", initial_sidebar_state="collapsed")

FORM_KEY_PREFIXES = ("p_", "s_", "ed_")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
def init_state() -> None:
    defaults = {
        "step": STEP_HOME, "photos": [], "uploader_gen": 0, "upload_msgs": [], "content": None,
        "content_sig": "", "variant": 0, "result": None, "video_bytes": None, "render_sig": "",
        "sid": uuid.uuid4().hex[:10], "music_upload": None, "music_msgs": [], "disclaimer": "",
        "p_title": "", "p_location": "", "p_price": "", "p_category": "Apartment", "p_bedrooms": 0,
        "p_bathrooms": 0, "p_area": "", "p_description": "", "p_amenities": "", "p_contact": "",
        "p_cta": "", "s_aspect": list(config.ASPECT_RATIOS)[0], "s_res": "720p",
        "s_theme": "Luxury Editorial", "s_duration": 30, "s_music": "No music", "s_use_ai": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    # Streamlit drops widget state for widgets that are not drawn on the current step;
    # re-assigning keeps form values alive while the user moves between steps.
    for key in list(st.session_state.keys()):
        if key.startswith(FORM_KEY_PREFIXES):
            st.session_state[key] = st.session_state[key]


def current_info() -> PropertyInfo:
    ss = st.session_state
    return PropertyInfo.from_dict({
        "title": ss.p_title, "location": ss.p_location, "price": ss.p_price, "category": ss.p_category,
        "bedrooms": ss.p_bedrooms, "bathrooms": ss.p_bathrooms, "area": ss.p_area,
        "description": ss.p_description, "amenities": parse_amenities(ss.p_amenities),
        "contact": ss.p_contact, "cta_text": ss.p_cta,
    })


def current_settings(music_path: str | None = None) -> RenderSettings:
    ss = st.session_state
    return RenderSettings(
        aspect=config.ASPECT_RATIOS[ss.s_aspect], resolution=ss.s_res, duration=int(ss.s_duration),
        theme=ss.s_theme, music_path=music_path, disclaimer=ss.disclaimer.strip(),
    )


def photo_pairs() -> list[tuple[str, bytes]]:
    return [(p["name"], p["data"]) for p in st.session_state.photos]


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------
def go(step: int) -> None:
    st.session_state.step = step


def load_sample() -> None:
    ss = st.session_state
    data = json.loads(SAMPLE_JSON.read_text(encoding="utf-8"))
    ss.p_title, ss.p_location, ss.p_price = data["title"], data["location"], data["price"]
    ss.p_category = data["category"]
    ss.p_bedrooms, ss.p_bathrooms = int(data.get("bedrooms") or 0), int(data.get("bathrooms") or 0)
    ss.p_area, ss.p_description = data.get("area", ""), data.get("description", "")
    ss.p_amenities = ", ".join(data.get("amenities", []))
    ss.p_contact, ss.p_cta = data.get("contact", ""), data.get("cta_text", "")
    ss.photos = []
    for index in range(1, 5):
        path = config.SAMPLE_DIR / f"demo_visual_{index}.jpg"
        if path.exists():
            raw = path.read_bytes()
            ss.photos.append({"id": uuid.uuid4().hex[:8], "name": path.name, "data": raw, "thumb": thumbnail_bytes(raw)})
    ss.disclaimer = SAMPLE_DISCLAIMER
    ss.content, ss.content_sig, ss.variant = None, "", 0
    ss.result, ss.video_bytes = None, None
    ss.upload_msgs = []
    ss.step = STEP_PROPERTY


def _add_photo(name: str, raw: bytes, messages: list[str]) -> bool:
    check = check_image(name, raw)
    if not check.ok:
        messages.append(check.message)
        return False
    if check.warning:
        messages.append("⚠️ " + check.warning)
    st.session_state.photos.append({"id": uuid.uuid4().hex[:8], "name": name, "data": raw, "thumb": thumbnail_bytes(raw)})
    return True


def ingest_uploads() -> None:
    ss = st.session_state
    files = ss.get(f"uploader_{ss.uploader_gen}") or []
    messages: list[str] = []
    existing = {hashlib.md5(p["data"]).hexdigest() for p in ss.photos}
    skipped_extra = 0
    for uploaded in files:
        raw = uploaded.getvalue()
        if hashlib.md5(raw).hexdigest() in existing:
            messages.append(f"'{uploaded.name}' is already in your list - skipped.")
            continue
        if len(ss.photos) >= config.MAX_IMAGES:
            skipped_extra += 1
            continue
        if _add_photo(uploaded.name, raw, messages):
            existing.add(hashlib.md5(raw).hexdigest())
    if skipped_extra:
        messages.append(f"Maximum {config.MAX_IMAGES} photographs: {skipped_extra} extra file(s) were not added.")
    ss.upload_msgs = messages
    ss.uploader_gen += 1


def replace_photo(photo_id: str) -> None:
    ss = st.session_state
    files = ss.get(f"replace_{photo_id}")
    if not files:
        return
    messages: list[str] = []
    raw = files.getvalue()
    check = check_image(files.name, raw)
    if not check.ok:
        ss.upload_msgs = [check.message]
        return
    for photo in ss.photos:
        if photo["id"] == photo_id:
            photo.update(id=uuid.uuid4().hex[:8], name=files.name, data=raw, thumb=thumbnail_bytes(raw))
            break
    if check.warning:
        messages.append("⚠️ " + check.warning)
    ss.upload_msgs = messages


def remove_photo(photo_id: str) -> None:
    st.session_state.photos = [p for p in st.session_state.photos if p["id"] != photo_id]
    st.session_state.upload_msgs = []


def move_photo(photo_id: str, delta: int) -> None:
    photos = st.session_state.photos
    index = next((i for i, p in enumerate(photos) if p["id"] == photo_id), None)
    if index is None or not 0 <= index + delta < len(photos):
        return
    photos[index], photos[index + delta] = photos[index + delta], photos[index]


def clear_photos() -> None:
    st.session_state.photos = []
    st.session_state.upload_msgs = []


def ingest_music() -> None:
    ss = st.session_state
    uploaded = ss.get("s_music_file")
    ss.music_msgs = []
    ss.music_upload = None
    if uploaded is None:
        return
    raw = uploaded.getvalue()
    check = validate_music(uploaded.name, data=raw)
    if check.ok:
        ss.music_upload = (uploaded.name, raw)
        ss.music_msgs = ["⚠️ " + w for w in check.warnings]
    else:
        ss.music_msgs = check.errors + ["The video will be rendered without music."]


# ---------------------------------------------------------------------------
# Content helpers
# ---------------------------------------------------------------------------
def content_signature(info: PropertyInfo, scene_count: int, use_ai: bool) -> str:
    payload = json.dumps([info.to_dict(), scene_count, use_ai], sort_keys=True, default=str)
    return hashlib.md5(payload.encode()).hexdigest()


def generate_now(variant: int) -> None:
    ss = st.session_state
    info = current_info()
    scene_count = count_photo_scenes(len(ss.photos), int(ss.s_duration))
    use_ai = bool(ss.s_use_ai and config.gemini_api_key())
    content = generate_content(info, scene_count, variant=variant, use_ai=use_ai)
    ss.content, ss.variant = content, variant
    ss.content_sig = content_signature(info, scene_count, use_ai)
    ss.ed_headline, ss.ed_hook, ss.ed_closing = content.headline, content.hook, content.closing
    ss.ed_script, ss.ed_social = content.script, content.social_description
    for index, caption in enumerate(content.scene_captions):
        ss[f"ed_cap_{index}"] = caption


def regenerate() -> None:
    generate_now(st.session_state.variant + 1)


def edited_content() -> GeneratedContent:
    ss = st.session_state
    base: GeneratedContent = ss.content
    captions = [ss.get(f"ed_cap_{i}", c) for i, c in enumerate(base.scene_captions)]
    return replace(base, headline=ss.ed_headline.strip() or base.headline, hook=ss.ed_hook.strip() or base.hook,
                   closing=ss.ed_closing.strip() or base.closing, script=ss.ed_script, social_description=ss.ed_social,
                   scene_captions=[c.strip() for c in captions])


def render_signature() -> str:
    ss = st.session_state
    payload = json.dumps([
        current_info().to_dict(), [hashlib.md5(p["data"]).hexdigest() for p in ss.photos],
        ss.s_aspect, ss.s_res, ss.s_duration, ss.s_theme, ss.s_music, ss.disclaimer,
        [ss.get(k) for k in ("ed_headline", "ed_hook", "ed_closing")],
        [ss.get(f"ed_cap_{i}") for i in range(8)],
    ], default=str)
    return hashlib.md5(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------
def nav_buttons(back: int | None, forward: int | None, forward_label: str = "Continue →", disabled: bool = False) -> None:
    left, _, right = st.columns([1, 3, 1.4])
    if back is not None:
        left.button("← Back", on_click=go, args=(back,), width="stretch", key=f"back_{back}_{forward}")
    if forward is not None:
        right.button(forward_label, on_click=go, args=(forward,), type="primary", disabled=disabled,
                     width="stretch", key=f"fwd_{back}_{forward}")


def step_home() -> None:
    ui.hero()
    st.write("")
    c1, c2, _ = st.columns([1.3, 1.3, 2.5])
    c1.button("Create Property Video  →", type="primary", on_click=go, args=(STEP_PROPERTY,), width="stretch", key="cta_home")
    c2.button("Try with sample listing", on_click=load_sample, width="stretch", key="sample_home",
              help="Fills in a fictional demo property and four synthetic images.")
    st.write("")
    ui.feature_cards()
    st.write("")
    ui.section("See what it produces", "A real MP4 rendered by this application's own engine from a fictional, synthetic listing.", "Demo")
    left, right = st.columns([1, 1.25], gap="large")
    with left:
        if SAMPLE_VIDEO.exists():
            st.video(str(SAMPLE_VIDEO))
        else:
            ui.note("The sample video has not been generated yet. Run <code>python tools/build_sample_video.py</code>.")
    with right:
        ui.raw("""
        <div class="pv-card"><h4>How it works</h4>
        <p>① Enter the property details you have — everything optional except a title or location.<br>
        ② Upload 4–8 photographs and arrange their order.<br>
        ③ Pick a format, theme and duration (optional background music).<br>
        ④ Review and edit the generated headline, captions and call to action.<br>
        ⑤ Render, preview and download your H.264 MP4.</p></div>
        """)
        st.write("")
        ui.note("The demo uses illustrative synthetic images and a fictional listing — not real property photographs.")


def step_property() -> None:
    ui.section("Property details", "Only a title or a location is required. Anything you leave blank is simply left out of the video.", "Step 1")
    top_left, top_right = st.columns([4, 1])
    top_right.button("Load sample", on_click=load_sample, width="stretch", key="sample_prop")
    residential = st.session_state.p_category in config.RESIDENTIAL_CATEGORIES

    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.text_input("Property title", key="p_title", max_chars=config.MAX_TITLE_CHARS, placeholder="e.g. Skyline Residency")
        c2.text_input("Location", key="p_location", max_chars=config.MAX_LOCATION_CHARS, placeholder="e.g. Gachibowli, Hyderabad")
        c3, c4 = st.columns(2)
        c3.text_input("Price", key="p_price", max_chars=config.MAX_PRICE_CHARS, placeholder="e.g. ₹85 Lakhs")
        c4.selectbox("Property category", config.PROPERTY_CATEGORIES, key="p_category")
        c5, c6, c7 = st.columns(3)
        c5.number_input("Bedrooms (0 = not specified)", min_value=0, max_value=50, step=1, key="p_bedrooms", disabled=not residential)
        c6.number_input("Bathrooms (0 = not specified)", min_value=0, max_value=50, step=1, key="p_bathrooms", disabled=not residential)
        c7.text_input("Area (optional)", key="p_area", max_chars=config.MAX_AREA_CHARS, placeholder="e.g. 1,650 sq ft")
        st.text_area("Short description (optional)", key="p_description", max_chars=config.MAX_DESCRIPTION_CHARS, height=100,
                     placeholder="Write short, factual sentences. They may be used as captions.")
        st.text_area("Amenities & highlights (optional)", key="p_amenities", height=90,
                     placeholder="Modular kitchen, Balcony, Covered parking",
                     help=f"Separate with commas or new lines (maximum {config.MAX_AMENITIES}).")
        c8, c9 = st.columns(2)
        c8.text_input("Contact number / email (optional)", key="p_contact", max_chars=config.MAX_CONTACT_CHARS, placeholder="+91-XXXXXXXXXX")
        c9.text_input("Call-to-action text (optional)", key="p_cta", max_chars=config.MAX_CTA_CHARS,
                      placeholder="Leave empty for an automatic closing line")

    result = validate_property(current_info())
    for message in result.errors:
        st.error(message)
    for message in result.warnings:
        st.info(message, icon="ℹ️")
    nav_buttons(STEP_HOME, STEP_PHOTOS, disabled=not result.ok)


def step_photos() -> None:
    ss = st.session_state
    ui.section("Photo studio", f"Upload {config.MIN_IMAGES}–{config.MAX_IMAGES} photographs (JPG, JPEG, PNG or WEBP). "
               "The order below is the order of the scenes — the first photo becomes the opening shot.", "Step 2")
    with st.container(border=True):
        st.file_uploader("Drop photographs here or browse", accept_multiple_files=True, key=f"uploader_{ss.uploader_gen}",
                         on_change=ingest_uploads, help="Photos stay on this computer.")
        for message in ss.upload_msgs:
            (st.warning if message.startswith("⚠️") else st.error)(message)

        count = len(ss.photos)
        st.progress(min(count / config.MAX_IMAGES, 1.0), text=f"{count} of {config.MAX_IMAGES} photographs "
                    f"(minimum {config.MIN_IMAGES})")
        if ss.photos:
            columns = st.columns(4)
            for index, photo in enumerate(ss.photos):
                with columns[index % 4]:
                    ui.raw(f'<span class="pv-thumb-num">{"Hero · " if index == 0 else ""}Photo {index + 1}</span>')
                    st.image(photo["thumb"], width="stretch")
                    st.caption(photo["name"])
                    b1, b2, b3 = st.columns(3)
                    b1.button("◀", key=f"l_{photo['id']}", on_click=move_photo, args=(photo["id"], -1),
                              disabled=index == 0, help="Move earlier", width="stretch")
                    b2.button("▶", key=f"r_{photo['id']}", on_click=move_photo, args=(photo["id"], 1),
                              disabled=index == count - 1, help="Move later", width="stretch")
                    b3.button("✕", key=f"x_{photo['id']}", on_click=remove_photo, args=(photo["id"],),
                              help="Remove", width="stretch")
                    with st.popover("Replace", width="stretch"):
                        st.file_uploader("Choose a replacement", key=f"replace_{photo['id']}",
                                         on_change=replace_photo, args=(photo["id"],), label_visibility="collapsed")
            st.button("Clear all photographs", on_click=clear_photos, key="clear_photos")

    result, _ = validate_images(photo_pairs())
    for message in result.errors:
        st.error(message) if ss.photos else st.info(message)
    for message in result.warnings:
        st.warning(message)
    nav_buttons(STEP_PROPERTY, STEP_STYLE, disabled=not result.ok)


def step_style() -> None:
    ss = st.session_state
    ui.section("Creative settings", "Choose the format, look and length of your video.", "Step 3")
    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.radio("Aspect ratio", list(config.ASPECT_RATIOS), key="s_aspect",
                 captions=["Instagram Reels · YouTube Shorts", "YouTube · property presentations"])
        c2.radio("Resolution", list(config.RESOLUTIONS), key="s_res", horizontal=True,
                 captions=["Faster to render", "Sharper, slower"])
        c2.radio("Duration", list(config.DURATIONS), key="s_duration", horizontal=True, format_func=lambda s: f"{s} seconds")
        st.radio("Visual theme", list(THEMES), key="s_theme", horizontal=True)
        theme = THEMES[ss.s_theme]
        ui.theme_card(theme.name, theme.accent, THEME_BLURBS[theme.name])
        st.write("")
        st.text_input("Small on-screen note (optional)", key="disclaimer", max_chars=90,
                      placeholder="e.g. Images are for illustration only",
                      help="Shown small at the bottom of every scene.")

    with st.container(border=True):
        st.radio("Background music", list(MUSIC_MODES), key="s_music", horizontal=True)
        if MUSIC_MODES[ss.s_music] == "upload":
            st.file_uploader("Music file (MP3, WAV, M4A, AAC, OGG, FLAC)", key="s_music_file", on_change=ingest_music)
            for message in ss.music_msgs:
                (st.warning if message.startswith("⚠️") else st.error)(message)
            if ss.music_upload:
                st.success(f"Music ready: {ss.music_upload[0]}")
        elif MUSIC_MODES[ss.s_music] == "ambient":
            st.caption("A calm pad generated on your computer - no licensing issues. It fades in and out automatically.")
        st.caption("You are responsible for having the rights to any music you upload.")

    specs = plan_scenes(len(ss.photos), int(ss.s_duration)) if ss.photos else []
    if specs:
        used, total = photos_used(specs), len(ss.photos)
        ui.note(f"Storyboard: {len(specs)} scenes (intro, {len(specs) - 2} photo scenes, closing) · "
                f"{used} of {total} photographs shown at {ss.s_duration}s.")
        if used < total:
            st.warning("Some photographs do not fit at this duration. Choose a longer duration to show all of them.")
    nav_buttons(STEP_PHOTOS, STEP_CONTENT)


def step_content() -> None:
    ss = st.session_state
    ui.section("Content studio", "Review and edit the generated copy. Only your own details are used.", "Step 4")
    info = current_info()
    scene_count = count_photo_scenes(len(ss.photos), int(ss.s_duration))
    has_key = bool(config.gemini_api_key())

    with st.container(border=True):
        t1, t2, t3 = st.columns([1.6, 1.3, 1])
        if has_key:
            t1.toggle("Use Gemini (optional LLM)", key="s_use_ai", help="Falls back to the rule-based engine on any problem.")
        else:
            t1.caption("No GEMINI_API_KEY set - using the offline rule-based engine (see README to enable Gemini).")
        use_ai = bool(ss.s_use_ai and has_key)
        signature = content_signature(info, scene_count, use_ai)
        if ss.content is None or ss.content_sig != signature:
            generate_now(0)
        content: GeneratedContent = ss.content
        t2.markdown(ui.engine_pill(content.engine), unsafe_allow_html=True)
        t3.button("↻ Regenerate", on_click=regenerate, width="stretch", key="regen")
        st.caption(content.engine_detail)
        for message in content.notes:
            st.warning(message)

    left, right = st.columns([1.15, 1], gap="large")
    with left:
        with st.container(border=True):
            st.text_input("Video headline", key="ed_headline", max_chars=90)
            st.text_input("Opening hook", key="ed_hook", max_chars=90)
            specs = [s for s in plan_scenes(len(ss.photos), int(ss.s_duration)) if s.kind == "photo"]
            st.markdown("**Scene captions**")
            for index in range(len(content.scene_captions)):
                col_a, col_b = st.columns([1, 4])
                if index < len(specs) and specs[index].photo_index < len(ss.photos):
                    col_a.image(ss.photos[specs[index].photo_index]["thumb"], width="stretch")
                col_b.text_input(f"Scene {index + 2} caption", key=f"ed_cap_{index}", max_chars=110)
            st.text_input("Closing call to action", key="ed_closing", max_chars=config.MAX_CTA_CHARS)
    with right:
        with st.container(border=True):
            st.text_area("Promotional script (text only - no voice-over is generated)", key="ed_script", height=210)
            st.text_area("Social media description", key="ed_social", height=230)
        ui.note("<b>What is AI here?</b> " + ("Copy written by Google Gemini and checked by a factuality guard. " if content.engine == "gemini" else
                "The copy comes from a deterministic rule-based template engine — <b>not an AI language model</b>. ")
                + "Layout, motion, transitions and rendering are ordinary code, not AI.")
    nav_buttons(STEP_STYLE, STEP_EXPORT, forward_label="Continue to render →")


def run_render() -> None:
    ss = st.session_state
    info, content = current_info(), edited_content()
    mode = MUSIC_MODES[ss.s_music]
    status = st.empty()
    bar = st.progress(0.0, text="Starting…")

    def update(fraction: float, stage: str) -> None:
        bar.progress(min(max(fraction, 0.0), 1.0), text=f"{stage}  ·  {int(fraction * 100)}%")

    try:
        cleanup_old_uploads()
        paths = save_photos(photo_pairs(), ss.sid)
        music_path, music_warnings = prepare_music(mode, ss.sid, int(ss.s_duration), ss.music_upload)
        settings = current_settings(music_path)
        result = render_video(paths, info, content, settings, output_path_for(info), progress=update)
        result.warnings = music_warnings + result.warnings
        ss.result = result
        ss.video_bytes = Path(result.path).read_bytes()
        ss.render_sig = render_signature()
        bar.empty()
        status.success("Your video is ready.")
    except RenderError as exc:
        bar.empty()
        status.error(f"The video could not be rendered. {exc}")
    except Exception as exc:  # noqa: BLE001 - keep the app alive and explain
        bar.empty()
        status.error("Something unexpected went wrong while rendering. Your inputs are safe - please try again.")
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(exc)))


def regenerate_and_render() -> None:
    regenerate()
    st.session_state.trigger_render = True


def step_export() -> None:
    ss = st.session_state
    ui.section("Render & export", "Generate the final MP4, preview it here and download it.", "Step 5")
    if ss.content is None:
        go(STEP_CONTENT)
        st.rerun()

    settings = current_settings()
    width, height = settings.size
    specs = plan_scenes(len(ss.photos), settings.duration)
    with st.container(border=True):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Format", f"{settings.aspect} · {width}×{height}")
        m2.metric("Duration", f"{settings.duration} s")
        m3.metric("Theme", settings.theme)
        m4.metric("Scenes", f"{len(specs)} · {photos_used(specs)}/{len(ss.photos)} photos")
        b1, b2, _ = st.columns([1.3, 1.3, 2])
        clicked = b1.button("🎬 Generate Video", type="primary", width="stretch", key="gen_video")
        b2.button("↻ New variation + render", on_click=regenerate_and_render, width="stretch", key="gen_variation",
                  help="Writes different caption wording, then renders again.")

    if ss.pop("trigger_render", False) or clicked:
        run_render()

    if ss.result is not None and ss.video_bytes:
        result = ss.result
        stale = ss.render_sig != render_signature()
        if stale:
            st.warning("Your settings or content changed after this video was rendered. Generate again to update it.")
        for message in result.warnings:
            st.warning(message)
        left, right = st.columns([1, 1.2], gap="large")
        with left:
            st.video(ss.video_bytes, format="video/mp4")
        with right:
            with st.container(border=True):
                st.markdown("#### Your video")
                a, b = st.columns(2)
                a.metric("Duration", f"{result.duration:.1f} s")
                b.metric("Resolution", f"{result.width}×{result.height}")
                c, d = st.columns(2)
                c.metric("Aspect ratio", "9:16" if result.height > result.width else "16:9")
                d.metric("File size", f"{result.size_bytes / 1_048_576:.1f} MB")
                st.caption(f"H.264 · {result.fps} fps · {'with' if result.has_audio else 'no'} audio track · saved as {Path(result.path).name}")
                try:
                    st.download_button("⬇ Download MP4", ss.video_bytes, file_name=Path(result.path).name, mime="video/mp4",
                                       type="primary", width="stretch", on_click="ignore", key="download_mp4")
                except TypeError:   # older Streamlit without on_click="ignore"
                    st.download_button("⬇ Download MP4", ss.video_bytes, file_name=Path(result.path).name, mime="video/mp4",
                                       type="primary", width="stretch", key="download_mp4")
            st.button("← Edit captions", on_click=go, args=(STEP_CONTENT,), key="back_to_content")
    nav_buttons(STEP_CONTENT, None)


# ---------------------------------------------------------------------------
def main() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    config.ensure_dirs()
    step = st.session_state.step
    ui.topbar(step)
    {STEP_HOME: step_home, STEP_PROPERTY: step_property, STEP_PHOTOS: step_photos,
     STEP_STYLE: step_style, STEP_CONTENT: step_content, STEP_EXPORT: step_export}[step]()
    ui.raw('<div class="pv-muted" style="margin-top:2.5rem;font-size:.78rem;text-align:center">PropVision AI · '
           'Copy is rule-based unless Gemini is enabled · Videos use only the details you provide.</div>')


main()
