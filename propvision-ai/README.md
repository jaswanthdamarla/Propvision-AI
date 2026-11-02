# PropVision AI
**Turn Property Listings into Professional Real Estate Videos with AI.**

PropVision AI turns property details and 4–8 photographs into a captioned, animated MP4 (Ken Burns motion, gradient overlays, animated typography, transitions, optional music) that you can preview and download from a dark, SaaS-style Streamlit app. It runs locally with **no API key and no paid service**.

## Problem statement
Agents and owners need short marketing videos for every listing, but editing them by hand is slow, and generic AI copy tends to invent amenities, distances and claims. PropVision AI automates the video and writes copy **only from the facts you enter**.

## Features
- Property form where everything except a title *or* a location is optional.
- Photo studio: JPG/JPEG/PNG/WEBP, 4–8 photos, thumbnails, reorder, remove, replace, clear validation messages.
- Four themes (Luxury Editorial, Modern Minimal, Warm & Welcoming, Bold Contemporary), 9:16 or 16:9, 720p/1080p, 20/30/40 s.
- Smart storyboard: intro → photo scenes → closing CTA, paced to the duration; photos with very different aspect ratios are shown whole on a blurred backdrop instead of being badly cropped.
- Content Studio: headline, hook, script, per-scene captions, CTA and social description, all editable before rendering.
- Real renderer: every frame is composed (zoom/pan, overlays, text animation, cross-dissolve or slide) and encoded to H.264 MP4 with FFmpeg; progress and stage are shown live.
- Music: none, a built-in synthesised ambient pad, or your own file (validated; falls back to silent if unusable).
- Safe failures: bad input, corrupt photos, bad music or FFmpeg errors give readable messages, never a crash or a half-written file.

## Screenshots / demo
`sample_data/propvision_sample_demo.mp4` is a 30 s 9:16 demo rendered by this exact engine (it is also shown on the app's home page). Its pictures are **illustrative synthetic images**, not real property photographs.

## Technology stack
Python 3.11+ · Streamlit · Pillow · NumPy · FFmpeg via imageio-ffmpeg (libx264 + AAC) · python-dotenv · pytest · optional Google Gemini REST API.

## Architecture
```
app.py     Streamlit UI (step wizard)        ui/     CSS + HTML components
core/      config, models, validator, storyboard, content_engine, pipeline
video/     renderer (Ken Burns, transitions, FFmpeg), scenes (layouts), text_layout, themes, ambient
tools/     make_demo_images.py, build_sample_video.py
tests/     validator, content engine, storyboard, renderer, UI-flow tests
```
Flow: UI → validator → content engine → storyboard → renderer → FFmpeg. Each layer is independent and unit-tested.

## Project folder structure
```
propvision-ai/
├── app.py  requirements.txt  README.md  .env.example  .gitignore  LICENSE-NOTICE.txt
├── Launch-PropVision.command  Launch-PropVision-Windows.bat
├── .streamlit/config.toml
├── core/   config, models, validator, storyboard, content_engine, pipeline
├── video/  renderer, scenes, text_layout, themes, ambient
├── ui/     styles, components
├── assets/ fonts (Poppins, Lora) · music/
├── sample_data/  sample_property.json, demo_visual_1-4.jpg, propvision_sample_demo.mp4
├── tools/  tests/  uploads/  output/
```

## Installation - macOS
```bash
cd propvision-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
Or double-click **Launch-PropVision.command** (if macOS blocks it: right-click → Open once, or run `chmod +x Launch-PropVision.command`). It creates the virtual environment, installs dependencies and starts the app. Python 3.11+ is recommended (`brew install python@3.11`). A separate FFmpeg install is normally not needed; if the bundled one cannot be used, the app falls back to `ffmpeg` on your PATH (`brew install ffmpeg`).

## Installation - Windows
```bat
cd propvision-ai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
Or double-click **Launch-PropVision-Windows.bat**.

## How to run / generate a video
1. `streamlit run app.py` (opens http://localhost:8501).
2. Click **Create Property Video** (or **Try with sample listing** to fill everything in).
3. Property details → Photos (4–8) → Style (format, theme, duration, music) → Content (edit captions) → **Generate Video**.
4. Preview in the page, then **Download MP4**. Files are also saved in `output/`.

Rendering a 30 s 720p video took about 20 s in testing; 1080p takes longer.

## Sample data
- `sample_data/sample_property.json` - fictional listing ("Skyline Residency"; fake phone and e-mail).
- `sample_data/demo_visual_1..4.jpg` - synthetic illustrations (regenerate: `python tools/make_demo_images.py`).
- `sample_data/propvision_sample_demo.mp4` - regenerate: `python tools/build_sample_video.py [theme] [9:16|16:9] [720p|1080p]`.

## AI integration - what is and is not AI
| Part | How it works |
|---|---|
| Headline, hook, captions, script, CTA, social text | **Default: rule-based templates** (deterministic Python). Optional: **Google Gemini** (a real LLM) when you set `GEMINI_API_KEY` and switch it on in the Content Studio. |
| Layout, Ken Burns motion, transitions, rendering, music synthesis | Ordinary code, no AI model. |
| Voice-over | Not generated (the script is text only). |

The UI labels which engine produced the copy. Despite the product tagline, the default text engine is **not** an LLM.

## Rule-based fallback
`core/content_engine.py` builds copy from templates that restate your inputs (for example "A 3-bedroom apartment with 3 bathrooms." or "Highlights: modular kitchen, balcony and covered parking."). It never adds adjectives, nearby places, returns, approvals or availability. Variation comes from the **Regenerate** button. If Gemini is off, has no key, is offline, returns the wrong number of captions, or fails the **factuality guard** (numbers not in your input, banned claim types such as investment/returns/nearby/schools, praise words you did not use), the rule-based engine is used automatically and the reason is shown. When Gemini is on, only your property *text* is sent to Google, never your photos.

## Environment variables (`.env`, optional)
| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Enables the optional Gemini engine. Never hard-coded. |
| `GEMINI_MODEL` | Model name (default `gemini-2.5-flash`). |
| `FFMPEG_BINARY` | Use a specific FFmpeg executable. |

## Known limitations
- The Gemini integration is covered by unit tests with mocked responses only; it was **not run against the live API** during development.
- Built and tested on Linux (Python 3.13). It was **not run on a MacBook Air M2 or on Windows**; the stack is cross-platform, but the launchers are untested on those systems.
- Rendering runs in a single CPU thread inside the Streamlit request: the progress bar updates live, but the page is busy until the video is done. Encoding uses software x264, not the Apple hardware encoder.
- UI web fonts come from Google Fonts and need internet; offline the UI uses system fonts (videos use the bundled fonts).
- With short durations and many photos, not every photo fits; the app tells you and suggests a longer duration.
- Latin text and ₹ are supported in video text; other scripts (e.g. Devanagari, Telugu) are not supported by the bundled fonts.
- No voice-over and no HEIC support. Files live in local `uploads/` (auto-cleaned after 24 h) and `output/`.

## Testing
```bash
source .venv/bin/activate
python -m pytest -q
```
The suite (about 95 tests, ~2 minutes) covers validation edge cases (missing fields, 0–12 photos, unsupported/fake/huge images, bad music), the content engine's no-invention rules, storyboard pacing, full renders (both aspect ratios, mixed photo shapes, music mux, invalid-music fallback, corrupt-photo error, long text) and headless UI flows via Streamlit AppTest.

## Future improvements
Text-to-speech voice-over, hardware-accelerated encoding (VideoToolbox), background render worker, more themes and languages, logo/agent branding, per-scene photo assignment, HEIC input.
