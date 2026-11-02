"""Small HTML building blocks rendered with st.markdown(unsafe_allow_html=True)."""
from __future__ import annotations

import html

import streamlit as st

STEPS = ["Home", "Property", "Photos", "Style", "Content", "Export"]


def _md(markup: str) -> None:
    # collapse blank lines / indentation so Markdown never treats the HTML as a code block
    cleaned = "\n".join(line.strip() for line in markup.strip().splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


def topbar(step: int) -> None:
    _md(f"""
    <div class="pv-topbar">
      <div class="pv-brand"><div class="pv-logo">P</div><span>PropVision <span style="color:#d9b56d">AI</span></span></div>
      <span class="pv-chip">Real-estate video studio</span>
    </div>
    """)
    if step > 0:
        pills = []
        for index, name in enumerate(STEPS[1:], start=1):
            state = "active" if index == step else ("done" if index < step else "")
            mark = "✓" if index < step else str(index)
            pills.append(f'<div class="pv-step {state}"><span class="n">{mark}</span>{html.escape(name)}</div>')
        _md('<div class="pv-steps">' + "".join(pills) + "</div>")


def hero() -> None:
    _md("""
    <div class="pv-hero">
      <span class="pv-kicker">AI-assisted marketing video</span>
      <h1>Turn Property Listings into <em>Professional Real Estate Videos</em> with AI.</h1>
      <p>Enter your property details, add 4–8 photographs and get a cinematic, captioned MP4 — Ken Burns motion,
      elegant typography and smooth transitions — ready for Reels, Shorts and listings.
      Everything only uses the facts you provide.</p>
      <div class="pv-badges">
        <span class="pv-chip">Runs locally</span><span class="pv-chip">No API key needed</span>
        <span class="pv-chip">H.264 MP4 export</span><span class="pv-chip">9:16 &amp; 16:9</span>
      </div>
    </div>
    """)


def feature_cards() -> None:
    features = [
        ("🎬", "Cinematic rendering", "Real frame-by-frame video: zoom, pan, gradient overlays and animated typography — not a static slideshow."),
        ("🧭", "Smart storyboard", "Photos are distributed across an intro, highlight scenes and a closing call-to-action, paced to your chosen duration."),
        ("✍️", "Fact-safe copy", "Headline, hook, captions and CTA are written only from your inputs. No invented amenities, prices or claims."),
        ("🎨", "Four visual themes", "Luxury Editorial, Modern Minimal, Warm &amp; Welcoming and Bold Contemporary — each with its own type and transitions."),
    ]
    columns = st.columns(len(features), gap="medium")
    for column, (icon, title, text) in zip(columns, features):
        with column:
            _md(f'<div class="pv-card"><div class="pv-icon">{icon}</div><h4>{title}</h4><p>{text}</p></div>')


def section(title: str, subtitle: str = "", kicker: str = "") -> None:
    parts = []
    if kicker:
        parts.append(f'<div class="pv-kicker">{html.escape(kicker)}</div>')
    parts.append(f'<div class="pv-section-title">{html.escape(title)}</div>')
    if subtitle:
        parts.append(f'<div class="pv-section-sub">{html.escape(subtitle)}</div>')
    _md("".join(parts))


def note(text: str) -> None:
    _md(f'<div class="pv-note">{text}</div>')


def theme_card(name: str, accent: tuple[int, int, int], description: str) -> None:
    color = "rgb({},{},{})".format(*accent)
    _md(f"""
    <div class="pv-theme"><div class="pv-swatch" style="background:linear-gradient(135deg,#0d1220,{color})"></div>
    <div><b>{html.escape(name)}</b><div class="pv-muted" style="font-size:.85rem">{html.escape(description)}</div></div></div>
    """)


def engine_pill(engine: str) -> str:
    if engine == "gemini":
        return '<span class="pv-pill-ai pv-pill-llm">LLM · Google Gemini</span>'
    return '<span class="pv-pill-ai pv-pill-rule">Rule-based · no AI model</span>'


def raw(markup: str) -> None:
    _md(markup)
