import re

import pytest

from core import content_engine as ce
from core.content_engine import ContentError, audit_ai_text, generate_content, generate_rule_based
from core.models import PropertyInfo, parse_amenities

SKYLINE = dict(title="Skyline Residency", location="Gachibowli, Hyderabad", price="₹85 Lakhs", category="Apartment",
               bedrooms=3, bathrooms=3, amenities=["Modular kitchen", "balcony", "Covered parking"],
               contact="+91-XXXXXXXXXX")


def info(**kw):
    data = dict(SKYLINE)
    data.update(kw)
    return PropertyInfo.from_dict(data)


def test_basic_generation_shape():
    content = generate_rule_based(info(), 4)
    assert content.engine == "rule-based"
    assert "Skyline Residency" in content.headline
    assert content.hook.endswith("?")
    assert len(content.scene_captions) == 4
    assert content.closing and content.script and content.social_description


def test_captions_are_unique_and_non_empty():
    for n in range(1, 10):
        captions = generate_rule_based(info(), n).scene_captions
        assert len(captions) == n
        assert all(captions)
        assert len({c.lower() for c in captions}) == len(captions), captions


def test_amenities_distributed_across_scenes():
    captions = generate_rule_based(info(), 5).scene_captions
    joined = " ".join(captions).lower()
    for amenity in ("modular kitchen", "balcony", "covered parking"):
        assert amenity in joined


def test_amenities_merge_when_few_scenes():
    captions = generate_rule_based(info(), 3).scene_captions
    joined = " ".join(captions).lower()
    assert "modular kitchen" in joined and "covered parking" in joined and "balcony" in joined


def test_type_fact_uses_only_supplied_numbers():
    caption = generate_rule_based(info(), 4).scene_captions[0]
    assert "3-bedroom apartment" in caption and "3 bathrooms" in caption


def test_no_bedrooms_means_no_bedroom_claim():
    content = generate_rule_based(info(bedrooms=None, bathrooms=None), 4)
    assert "bedroom" not in " ".join(content.scene_captions + [content.script]).lower()


def test_missing_everything_optional_still_works():
    content = generate_rule_based(PropertyInfo.from_dict({"title": "Green Villa", "category": "Villa"}), 4)
    text = " ".join(content.scene_captions + [content.script, content.closing, content.social_description])
    assert not re.search(r"\d", text)                      # no invented numbers
    assert "Green Villa" in content.headline


def test_missing_title_uses_neutral_title():
    content = generate_rule_based(info(title=""), 4)
    assert "Gachibowli" in content.headline and "None" not in content.headline


def test_missing_location_not_mentioned():
    content = generate_rule_based(info(location=""), 4)
    assert "Hyderabad" not in " ".join(content.scene_captions + [content.script, content.social_description])


def test_missing_price_not_mentioned():
    content = generate_rule_based(info(price=""), 4)
    assert "Lakh" not in content.script and "Lakh" not in content.social_description


def test_missing_contact_gives_generic_cta():
    content = generate_rule_based(info(contact=""), 4)
    assert "Contact:" not in content.script and content.closing


def test_custom_cta_is_respected():
    assert generate_rule_based(info(cta_text="Book a viewing this weekend"), 4).closing == "Book a viewing this weekend"


BANNED = ["invest", "return", "apprecia", "rera", "approved", "discount", "school", "hospital", "metro", "airport",
          "luxur", "spacious", "stunning", "premium", "limited time", "nearby", "walking distance"]


@pytest.mark.parametrize("variant", range(6))
def test_no_invented_claims_in_any_variant(variant):
    content = generate_rule_based(info(), 6, variant)
    blob = " ".join([content.headline, content.hook, content.script, content.closing, content.social_description,
                     *content.scene_captions]).lower()
    for word in BANNED:
        assert word not in blob, (word, blob)


def test_all_numbers_come_from_input():
    content = generate_rule_based(info(area="1,650 sq ft"), 6)
    blob = " ".join([content.script, content.social_description, *content.scene_captions])
    allowed = {"3", "85", "1", "650", "91"}
    assert set(re.findall(r"\d+", blob)) <= allowed


def test_deterministic_and_variants_differ():
    a = generate_rule_based(info(), 4, 0)
    b = generate_rule_based(info(), 4, 0)
    assert a == b
    assert any(generate_rule_based(info(), 4, v) != a for v in range(1, 6))


def test_commercial_and_land_hooks():
    assert "business" in generate_rule_based(info(category="Office Space"), 4).hook.lower()
    assert "land" in generate_rule_based(info(category="Land / Plot"), 4).hook.lower()


def test_parse_amenities():
    assert parse_amenities("Pool, gym\n- Lift; pool , ") == ["Pool", "gym", "Lift"]


# ---- AI path --------------------------------------------------------------
def test_generate_content_without_key_falls_back(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    content = generate_content(info(), 4, use_ai=True)
    assert content.engine == "rule-based" and content.notes


def test_audit_rejects_invented_claims():
    i = info()
    assert audit_ai_text(["Great investment with strong returns"], i)
    assert audit_ai_text(["A spacious home near the metro"], i)
    assert audit_ai_text(["Only 2 units left"], i)
    assert audit_ai_text(["A 3-bedroom apartment in Gachibowli"], i) is None


def test_gemini_response_validated(monkeypatch):
    i = info()
    good = dict(headline="Discover Skyline Residency", hook="Looking for a new home?", script="A 3-bedroom apartment.",
                scene_captions=["A 3-bedroom apartment.", "Modular kitchen.", "Balcony.", "Covered parking."],
                closing="Get in touch today.", social_description="Skyline Residency")
    assert ce._content_from_ai_dict(good, i, 4).engine == "gemini"
    bad = dict(good, scene_captions=["A", "B", "C"])
    with pytest.raises(ContentError):
        ce._content_from_ai_dict(bad, i, 4)
    invented = dict(good, scene_captions=["Near the airport.", "Modular kitchen.", "Balcony.", "Covered parking."])
    with pytest.raises(ContentError):
        ce._content_from_ai_dict(invented, i, 4)
