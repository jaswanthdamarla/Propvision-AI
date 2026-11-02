import pytest

from core.storyboard import count_photo_scenes, photos_used, plan_scenes


@pytest.mark.parametrize("photos", range(4, 9))
@pytest.mark.parametrize("duration", [20, 30, 40])
def test_plan_is_consistent(photos, duration):
    scenes = plan_scenes(photos, duration)
    assert scenes[0].kind == "intro" and scenes[-1].kind == "cta"
    assert abs(sum(s.duration for s in scenes) - duration) < 1e-6
    for s in scenes:
        assert 0 <= s.photo_index < photos
    middle = [s for s in scenes if s.kind == "photo"]
    assert all(2.7 <= s.duration <= 6.6 for s in middle)


def test_all_photos_used_when_duration_allows():
    assert photos_used(plan_scenes(8, 40)) == 8
    assert photos_used(plan_scenes(8, 30)) == 8


def test_subset_when_too_many_photos_for_duration():
    assert photos_used(plan_scenes(8, 20)) < 8


def test_four_photos_30s_matches_six_scene_structure():
    assert len(plan_scenes(4, 30)) == 6


def test_order_preserved_for_first_pass():
    indices = [s.photo_index for s in plan_scenes(8, 30) if s.kind == "photo" and not s.reuse]
    assert indices == sorted(indices)


def test_count_matches():
    assert count_photo_scenes(4, 30) == 4
