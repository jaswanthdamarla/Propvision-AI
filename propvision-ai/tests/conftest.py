import io
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def make_image_bytes(size=(1200, 900), fmt="JPEG", color=(120, 160, 200)) -> bytes:
    img = Image.new("RGB", size, color)
    # add some structure so crops look different
    for x in range(0, size[0], 40):
        img.paste((255 - color[0], color[1], 80), (x, 0, x + 10, size[1]))
    buffer = io.BytesIO()
    img.save(buffer, fmt)
    return buffer.getvalue()


@pytest.fixture
def img_bytes():
    return make_image_bytes
