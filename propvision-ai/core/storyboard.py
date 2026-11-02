"""Storyboard planning: how many scenes, which photo goes where, how long each lasts."""
from __future__ import annotations

import math

from .models import SceneSpec

INTRO_SECONDS = {20: 3.0, 30: 3.5, 40: 4.0}
CTA_SECONDS = {20: 4.0, 30: 4.5, 40: 5.0}
MIN_PHOTO_SCENE = 2.8
MAX_PHOTO_SCENE = 6.5


def plan_scenes(num_photos: int, total_seconds: int) -> list[SceneSpec]:
    """Plan intro + photo scenes + closing scene for ``num_photos`` photographs.

    * Photo 0 is the hero image used for the intro scene.
    * The remaining photos fill the middle scenes in upload order. If there are more
      photos than the duration can hold, an evenly spaced subset is used; if there are
      too few for comfortable pacing, photos are revisited with a different crop/motion.
    * The closing scene uses the last uploaded photo as a darkened backdrop.
    """
    if num_photos < 1:
        raise ValueError("At least one photograph is required to plan scenes.")

    intro = INTRO_SECONDS.get(total_seconds, 3.5)
    cta = CTA_SECONDS.get(total_seconds, 4.5)
    middle_seconds = max(total_seconds - intro - cta, MIN_PHOTO_SCENE)

    pool = list(range(1, num_photos)) or [0]
    k_min = max(1, math.ceil(middle_seconds / MAX_PHOTO_SCENE))
    k_max = max(1, math.floor(middle_seconds / MIN_PHOTO_SCENE))
    k = min(max(len(pool), k_min), k_max)

    chosen: list[tuple[int, bool]] = []     # (photo index, is_reuse)
    if k <= len(pool):
        if k == len(pool):
            picks = pool
        else:  # evenly spaced subset, order preserved
            step = (len(pool) - 1) / (k - 1) if k > 1 else 0
            picks = [pool[round(i * step)] for i in range(k)]
        chosen = [(p, False) for p in picks]
    else:
        chosen = [(p, False) for p in pool]
        extra = k - len(pool)
        # Revisit photos (starting with the hero) with a different crop and motion.
        revisit_order = [0] + pool
        for i in range(extra):
            chosen.append((revisit_order[i % len(revisit_order)], True))

    per_scene = middle_seconds / k
    scenes: list[SceneSpec] = [SceneSpec("intro", 0, intro, label="Intro")]
    for number, (photo_index, reuse) in enumerate(chosen, start=1):
        scenes.append(
            SceneSpec("photo", photo_index, per_scene, reuse=reuse,
                      label=f"Photo scene {number} (photo {photo_index + 1})")
        )
    scenes.append(SceneSpec("cta", num_photos - 1, cta, label="Closing"))
    return scenes


def count_photo_scenes(num_photos: int, total_seconds: int) -> int:
    return sum(1 for scene in plan_scenes(num_photos, total_seconds) if scene.kind == "photo")


def photos_used(scenes: list[SceneSpec]) -> int:
    return len({s.photo_index for s in scenes if s.kind in ("intro", "photo")})
