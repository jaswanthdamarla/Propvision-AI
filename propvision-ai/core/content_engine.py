"""Marketing content generation.

Two engines produce the same ``GeneratedContent`` structure:

* **Rule-based engine** (default, offline, deterministic). Template logic written in plain
  Python - it is *not* a language model. It only restates facts the user supplied.
* **Gemini engine** (optional). Calls Google's Gemini API when ``GEMINI_API_KEY`` is set and
  the user opts in. Its output passes a factuality guard (no new numbers, no banned claim
  types, correct caption count); if anything is wrong or the API fails, the rule-based
  engine is used instead.
"""
from __future__ import annotations

import json
import random
import re
import urllib.error
import urllib.request
from typing import Optional

from . import config
from .models import GeneratedContent, PropertyInfo

CATEGORY_NOUN = {
    "Apartment": "apartment",
    "Villa": "villa",
    "Independent House": "independent house",
    "Penthouse": "penthouse",
    "Townhouse": "townhouse",
    "Studio": "studio",
    "Farmhouse": "farmhouse",
    "Commercial Property": "commercial property",
    "Office Space": "office space",
    "Shop": "shop",
    "Land / Plot": "plot of land",
    "Other": "property",
}

NEUTRAL_FILLERS = [
    "Take a closer look.",
    "See it for yourself.",
    "Picture yourself here.",
    "A closer look at the property.",
]


class ContentError(Exception):
    """Raised when an AI-generated response cannot be used."""


# --------------------------------------------------------------------------
# Small text helpers
# --------------------------------------------------------------------------
def _cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _article(word: str) -> str:
    return "An" if word[:1].lower() in "aeiou" else "A"


def _join_list(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if p and p.strip()]


def _ensure_period(text: str) -> str:
    text = text.strip()
    return text if not text or text[-1] in ".!?" else text + "."


def _short_location(location: str) -> str:
    return location.split(",")[0].strip() if location else ""


# --------------------------------------------------------------------------
# Fact extraction (only what the user supplied)
# --------------------------------------------------------------------------
def type_fact(info: PropertyInfo) -> str:
    """e.g. 'A 3-bedroom apartment with 2 bathrooms.' - built from supplied fields only."""
    noun = CATEGORY_NOUN.get(info.category, info.category.lower())
    beds = info.bedrooms if info.is_residential else None
    baths = info.bathrooms if info.is_residential else None
    if beds:
        article = "An" if str(beds).startswith("8") or beds in (11, 18) else "A"
        phrase = f"{article} {beds}-bedroom {noun}"
    else:
        phrase = f"{_article(noun)} {noun}"
    if baths:
        phrase += f" with {_plural(baths, 'bathroom')}"
    return phrase + "."


def area_fact(info: PropertyInfo, rng: random.Random) -> str:
    if not info.area:
        return ""
    return rng.choice([f"Total area: {info.area}.", f"Area: {info.area}.", f"{_cap(info.area)} of space."])


def location_fact(info: PropertyInfo, rng: random.Random) -> str:
    if not info.location:
        return ""
    return rng.choice([f"Located in {info.location}.", f"Find it in {info.location}.", f"Address area: {info.location}."])


def amenity_caption(amenities: list[str], rng: random.Random) -> str:
    if len(amenities) == 1:
        item = amenities[0]
        return rng.choice([f"Highlight: {_lower_first(item)}.", f"{_cap(item)}.", f"Don't miss: {_lower_first(item)}."])
    joined = _join_list([_lower_first(a) for a in amenities])
    return rng.choice([f"Highlights: {joined}.", f"Features: {joined}.", f"Includes: {joined}."])


def hook_options(info: PropertyInfo) -> list[str]:
    if info.category in ("Commercial Property", "Office Space", "Shop"):
        return ["Looking for the right space for your business?", "Searching for a new business location?"]
    if info.category == "Land / Plot":
        return ["Looking for the right plot of land?", "Searching for land to call your own?"]
    if info.is_residential:
        return ["Looking for a new home?", "Ready to find your next home?", "Searching for the right place to call home?"]
    return ["Looking for your next property?", "Searching for the right property?"]


def headline_options(info: PropertyInfo) -> list[str]:
    if not info.title:
        noun = CATEGORY_NOUN.get(info.category, "property")
        where = f" in {_short_location(info.location)}" if info.location else ""
        return [f"Discover This {_cap(noun)}{where}", f"Introducing {_article(noun).lower()} {noun}{where}"]
    title = info.title
    if info.category in ("Commercial Property", "Office Space", "Shop"):
        return [f"Discover Your Next Space at {title}", f"Introducing {title}"]
    if info.category == "Land / Plot":
        return [f"Discover {title}", f"Introducing {title}"]
    if info.is_residential:
        return [f"Discover Your Next Home at {title}", f"Welcome Home to {title}", f"Introducing {title}"]
    return [f"Discover {title}", f"Introducing {title}"]


def closing_options(info: PropertyInfo) -> list[str]:
    if info.cta_text:
        return [info.cta_text]
    return ["Interested? Contact us today to learn more.", "Want to know more? Get in touch today.", "Interested? Get in touch today."]


# --------------------------------------------------------------------------
# Rule-based engine
# --------------------------------------------------------------------------
def generate_rule_based(info: PropertyInfo, num_photo_scenes: int, variant: int = 0) -> GeneratedContent:
    """Deterministic template engine. ``variant`` selects different phrasings."""
    rng = random.Random(f"{info.display_title}|{info.location}|{variant}")

    headline = rng.choice(headline_options(info))
    hook = rng.choice(hook_options(info))
    closing = rng.choice(closing_options(info))
    captions = _build_captions(info, max(1, num_photo_scenes), rng)

    script = _build_script(info, hook, headline, closing, rng)
    social = _build_social(info, headline, closing)
    return GeneratedContent(
        headline=headline,
        hook=hook,
        script=script,
        scene_captions=captions,
        closing=closing,
        social_description=social,
        engine="rule-based",
        engine_detail="Deterministic template engine (no AI model). Uses only the details you entered.",
    )


def _build_captions(info: PropertyInfo, slots: int, rng: random.Random) -> list[str]:
    amenity_units: list[list[str]] = [[a] for a in info.amenities]
    area = area_fact(info, rng)
    location = location_fact(info, rng)
    description = [s for s in _sentences(info.description) if len(s) <= 95]

    def total_units() -> int:
        return 1 + len(amenity_units) + bool(area) + bool(location) + len(description)

    # Shrink to the number of slots: merge amenities, then drop low-priority items.
    while total_units() > slots:
        if len(amenity_units) > 1:
            sizes = [len(a) + len(b) for a, b in zip(amenity_units, amenity_units[1:])]
            i = sizes.index(min(sizes))
            amenity_units[i:i + 2] = [amenity_units[i] + amenity_units[i + 1]]
        elif description:
            description.pop()
        elif location:
            location = ""
        elif area:
            area = ""
        else:
            break

    units = [type_fact(info)]
    units += [amenity_caption(group, rng) for group in amenity_units]
    if area:
        units.append(area)
    units += [_ensure_period(s) for s in description]
    if location:
        units.append(location)

    fillers = NEUTRAL_FILLERS[:]
    rng.shuffle(fillers)
    while len(units) < slots:
        units.append(fillers[(len(units) - 1) % len(fillers)])
    return units[:slots]


def _build_script(info: PropertyInfo, hook: str, headline: str, closing: str, rng: random.Random) -> str:
    parts = [hook, _ensure_period(headline), type_fact(info)]
    if info.amenities:
        parts.append(amenity_caption(info.amenities, rng))
    if info.area:
        parts.append(f"Area: {info.area}.")
    if info.location:
        parts.append(f"Located in {info.location}.")
    if info.price:
        parts.append(f"Price: {info.price}.")
    parts.append(_ensure_period(closing))
    if info.contact:
        parts.append(f"Contact: {info.contact}.")
    return " ".join(parts)


def _hashtag(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    return "#" + "".join(w.capitalize() for w in words) if words else ""


def _build_social(info: PropertyInfo, headline: str, closing: str) -> str:
    lines = [headline, "", type_fact(info)]
    if info.location:
        lines.append(f"📍 {info.location}")
    if info.price:
        lines.append(f"💰 {info.price}")
    if info.area:
        lines.append(f"📐 {info.area}")
    if info.amenities:
        lines.append("✔ " + ", ".join(info.amenities))
    lines += ["", _ensure_period(closing)]
    if info.contact:
        lines.append(f"📞 {info.contact}")
    tags = ["#RealEstate", "#PropertyListing", _hashtag(info.category)]
    tags += [_hashtag(part) for part in info.location.split(",")[:2]]
    unique: list[str] = []
    for tag in tags:
        if tag and tag.lower() not in {t.lower() for t in unique}:
            unique.append(tag)
    lines += ["", " ".join(unique)]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Gemini engine (optional) with a factuality guard
# --------------------------------------------------------------------------
BANNED_PATTERNS = [
    r"\binvest", r"\breturns?\b", r"\bappreciat", r"\broi\b", r"\brera\b", r"\bapproved?\b",
    r"\bapprovals?\b", r"\bdiscount", r"\boffers?\b", r"\blimited[- ]time\b", r"\bhurry\b",
    r"\bnear(by)?\b", r"\bclose to\b", r"\bminutes? (from|away|to)\b", r"\bwalking distance\b",
    r"\bschools?\b", r"\bhospitals?\b", r"\bmetro\b", r"\bairport\b", r"\bmall\b", r"\bit park\b",
    r"\bsold\b", r"\bavailable\b", r"\bready to move\b", r"\bguarantee",
]
PUFFERY_WORDS = [
    "luxurious", "luxury", "spacious", "stunning", "breathtaking", "premium", "prime", "exclusive",
    "affordable", "state-of-the-art", "world-class", "serene", "peaceful", "elegant", "perfect",
    "dream", "unmatched", "unbeatable", "magnificent", "lavish", "sprawling", "gorgeous",
    "thoughtfully", "functional", "private", "modern", "cozy", "bright", "airy", "stylish",
]


def _source_corpus(info: PropertyInfo) -> str:
    fields = [info.title, info.location, info.price, info.category, info.area, info.description,
              info.contact, info.cta_text, " ".join(info.amenities)]
    if info.bedrooms:
        fields.append(str(info.bedrooms))
    if info.bathrooms:
        fields.append(str(info.bathrooms))
    return " ".join(fields)


def audit_ai_text(texts: list[str], info: PropertyInfo) -> Optional[str]:
    """Return a reason string if AI text makes unsupported claims, else None."""
    corpus = _source_corpus(info)
    corpus_lower = corpus.lower()
    allowed_numbers = set(re.findall(r"\d+", corpus))
    for text in texts:
        lowered = text.lower()
        for pattern in BANNED_PATTERNS:
            if re.search(pattern, lowered) and not re.search(pattern, corpus_lower):
                return f"unsupported claim type ({pattern.strip(chr(92) + 'b')})"
        for word in PUFFERY_WORDS:
            if re.search(rf"\b{re.escape(word)}\b", lowered) and word not in corpus_lower:
                return f"descriptive claim not supplied by the user ('{word}')"
        for number in re.findall(r"\d+", text):
            if number not in allowed_numbers:
                return f"number '{number}' is not in the supplied details"
    return None


def _gemini_prompt(info: PropertyInfo, num_scenes: int) -> str:
    facts = {k: v for k, v in info.to_dict().items() if v not in ("", None, [])}
    if not info.is_residential:
        facts.pop("bedrooms", None)
        facts.pop("bathrooms", None)
    return (
        "You write short marketing copy for a real-estate video.\n"
        "STRICT RULES:\n"
        "1. Use ONLY the facts in the JSON below. Never invent features, prices, numbers, locations,\n"
        "   nearby places, distances, returns, approvals, availability or discounts.\n"
        "2. Do not add descriptive adjectives that are not in the facts (no 'spacious', 'luxurious', etc.).\n"
        "3. Each caption is one short sentence (max 12 words) and each caption must be different.\n"
        "4. Omit anything that is missing instead of guessing.\n"
        f"Return JSON with keys: headline (string), hook (a question, string), script (3-6 sentences),\n"
        f"scene_captions (array of EXACTLY {num_scenes} strings), closing (string, call to action),\n"
        "social_description (string, may include hashtags).\n\n"
        f"FACTS:\n{json.dumps(facts, ensure_ascii=False, indent=2)}"
    )


def generate_gemini(info: PropertyInfo, num_photo_scenes: int, variant: int = 0, timeout: int = 25) -> GeneratedContent:
    """Call the Gemini REST API. Raises ContentError on any problem."""
    key = config.gemini_api_key()
    if not key:
        raise ContentError("GEMINI_API_KEY is not set.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": _gemini_prompt(info, num_photo_scenes)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": min(0.4 + 0.15 * (variant % 4), 1.0),
        },
    }
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
    except urllib.error.HTTPError as exc:
        raise ContentError(f"Gemini API returned HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ContentError(f"Could not reach the Gemini API ({exc}).") from exc
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise ContentError("Gemini returned a response that could not be parsed.") from exc

    return _content_from_ai_dict(data, info, num_photo_scenes)


def _content_from_ai_dict(data: dict, info: PropertyInfo, num_photo_scenes: int) -> GeneratedContent:
    try:
        headline = str(data["headline"]).strip()
        hook = str(data["hook"]).strip()
        script = str(data["script"]).strip()
        captions = [str(c).strip() for c in data["scene_captions"]]
        closing = str(data["closing"]).strip()
        social = str(data.get("social_description", "")).strip()
    except (KeyError, TypeError) as exc:
        raise ContentError("The AI response is missing required fields.") from exc

    if len(captions) != num_photo_scenes or not all(captions):
        raise ContentError(f"Expected {num_photo_scenes} captions, got {len(captions)}.")
    if len(set(c.lower() for c in captions)) != len(captions):
        raise ContentError("The AI response repeated a caption.")
    if len(headline) > 90 or any(len(c) > 100 for c in captions) or not (headline and hook and closing):
        raise ContentError("The AI response had empty or overly long fields.")

    problem = audit_ai_text([headline, hook, script, closing, social, *captions], info)
    if problem:
        raise ContentError(f"Rejected by the factuality guard: {problem}.")
    if info.cta_text:
        closing = info.cta_text
    return GeneratedContent(
        headline=headline, hook=hook, script=script, scene_captions=captions, closing=closing,
        social_description=social or _build_social(info, headline, closing),
        engine="gemini", engine_detail=f"Generated by Google {config.GEMINI_MODEL}; passed the factuality guard.",
    )


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def generate_content(info: PropertyInfo, num_photo_scenes: int, variant: int = 0, use_ai: bool = False) -> GeneratedContent:
    """Generate content with the requested engine, falling back to rule-based on any failure."""
    if use_ai:
        try:
            return generate_gemini(info, num_photo_scenes, variant)
        except ContentError as exc:
            content = generate_rule_based(info, num_photo_scenes, variant)
            content.notes.append(f"AI generation was not used: {exc} The rule-based engine was used instead.")
            return content
    return generate_rule_based(info, num_photo_scenes, variant)
