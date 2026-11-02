"""Generate the synthetic, illustrative demo visuals used by the sample listing.

These are procedurally drawn illustrations (Pillow + NumPy) - not photographs of any real
property - so there are no copyright or privacy concerns. Run:

    python tools/make_demo_images.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sample_data"
W, H = 1600, 1200
SS = 2                                   # supersampling factor
CW, CH = W * SS, H * SS


def S(*values):
    return [v * SS for v in values]


def vgrad(width, height, stops):
    """Vertical gradient from [(pos 0..1, (r,g,b)), ...]."""
    y = np.linspace(0, 1, height)
    channels = []
    for c in range(3):
        channels.append(np.interp(y, [p for p, _ in stops], [col[c] for _, col in stops]))
    arr = np.stack(channels, axis=1)[:, None, :].repeat(width, axis=1)
    return Image.fromarray(arr.astype(np.uint8), "RGB")


def glow(img, center, radius, color, strength=0.8):
    """Additive radial glow."""
    cx, cy = center
    ys, xs = np.ogrid[:img.height, :img.width]
    dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2) / radius
    falloff = np.clip(1 - dist, 0, 1) ** 2 * strength
    arr = np.asarray(img).astype(np.float32)
    for c in range(3):
        arr[..., c] += falloff * color[c]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def soft_shadow(img, box, blur, alpha=110, offset=(0, 0)):
    layer = Image.new("L", img.size, 0)
    x0, y0, x1, y1 = box
    ImageDraw.Draw(layer).rounded_rectangle((x0 + offset[0], y0 + offset[1], x1 + offset[0], y1 + offset[1]), radius=blur, fill=alpha)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.paste(Image.new("RGB", img.size, (0, 0, 0)), (0, 0), layer)


def finish(img, name, label=True):
    img = img.resize((W, H), Image.LANCZOS)
    arr = np.asarray(img).astype(np.float32)
    rng = np.random.default_rng(5)
    arr += rng.normal(0, 2.2, arr.shape)                 # subtle film grain
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    # vignette
    ys, xs = np.ogrid[:H, :W]
    d = np.sqrt(((xs - W / 2) / (W / 2)) ** 2 + ((ys - H / 2) / (H / 2)) ** 2)
    vig = 1 - np.clip(d - 0.55, 0, 1) * 0.28
    img = Image.fromarray((np.asarray(img) * vig[..., None]).astype(np.uint8), "RGB")
    if label:
        draw = ImageDraw.Draw(img, "RGBA")
        font = ImageFont.load_default(20)
        text = "ILLUSTRATIVE SYNTHETIC IMAGE - NOT A REAL PHOTOGRAPH"
        tw = draw.textlength(text, font=font)
        draw.rounded_rectangle((W - tw - 40, H - 46, W - 14, H - 14), radius=8, fill=(0, 0, 0, 120))
        draw.text((W - tw - 27, H - 41), text, font=font, fill=(255, 255, 255, 215))
    img.save(OUT / name, quality=92, subsampling=0)
    print("wrote", OUT / name)


# --------------------------------------------------------------------------
def exterior():
    rng = random.Random(11)
    img = vgrad(CW, CH, [(0, (22, 36, 82)), (0.45, (120, 96, 140)), (0.68, (236, 140, 112)), (0.82, (255, 205, 140)), (1, (255, 214, 160))])
    img = glow(img, S(1180, 760), CW * 0.45, (255, 170, 90), 0.75)
    d = ImageDraw.Draw(img, "RGBA")

    # distant skyline (hazy)
    x = 0
    while x < 1600:
        w = rng.randint(50, 110)
        h = rng.randint(140, 330)
        d.rectangle(S(x, 820 - h, x + w, 840), fill=(88, 84, 122, 170))
        x += w + rng.randint(0, 14)
    x = 40
    while x < 1600:
        w = rng.randint(60, 120)
        h = rng.randint(90, 220)
        d.rectangle(S(x, 840 - h, x + w, 860), fill=(52, 54, 92, 215))
        x += w + rng.randint(4, 30)

    # main tower
    tx0, ty0, tx1, ty1 = 470, 150, 930, 900
    body = vgrad(CW, CH, [(0, (66, 82, 116)), (1, (36, 46, 74))])
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rectangle(S(tx0, ty0, tx1, ty1), fill=255)
    img.paste(body, (0, 0), mask)
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle(S(tx0, ty0, tx1, ty0 + 12), fill=(210, 214, 226, 255))
    rows, cols = 17, 7
    cw = (tx1 - tx0 - 40) / cols
    rh = (ty1 - ty0 - 80) / rows
    for r in range(rows):
        for c in range(cols):
            x0 = tx0 + 20 + c * cw + 6
            y0 = ty0 + 40 + r * rh + 6
            lit = rng.random() < 0.46
            color = (255, 214, 140, 245) if lit else (86, 110, 150, 235)
            d.rectangle(S(x0, y0, x0 + cw - 12, y0 + rh - 14), fill=color)
            if lit:
                d.rectangle(S(x0, y0, x0 + cw - 12, y0 + (rh - 14) * 0.35), fill=(255, 236, 190, 120))
        d.rectangle(S(tx0 + 8, ty0 + 40 + (r + 1) * rh - 7, tx1 - 8, ty0 + 40 + (r + 1) * rh - 3), fill=(200, 205, 220, 150))
    # side wing
    d.rectangle(S(930, 470, 1180, 900), fill=(52, 62, 92, 255))
    for r in range(8):
        for c in range(3):
            lit = rng.random() < 0.5
            x0, y0 = 950 + c * 76, 490 + r * 50
            d.rectangle(S(x0, y0, x0 + 56, y0 + 32), fill=(255, 214, 140, 240) if lit else (88, 112, 150, 230))
    d.rectangle(S(260, 640, 470, 900), fill=(44, 54, 84, 255))
    for r in range(5):
        for c in range(2):
            lit = rng.random() < 0.5
            x0, y0 = 285 + c * 90, 665 + r * 48
            d.rectangle(S(x0, y0, x0 + 66, y0 + 30), fill=(255, 214, 140, 240) if lit else (88, 112, 150, 230))

    # covered parking canopy + cars
    d.rectangle(S(1180, 720, 1560, 742), fill=(30, 34, 52, 255))
    for px in (1200, 1380, 1540):
        d.rectangle(S(px, 742, px + 12, 900), fill=(30, 34, 52, 255))
    for i, col in enumerate([(160, 40, 48), (210, 210, 218), (36, 60, 110)]):
        cx = 1230 + i * 120
        d.rounded_rectangle(S(cx, 838, cx + 100, 884), radius=14 * SS, fill=col + (255,))
        d.rounded_rectangle(S(cx + 18, 814, cx + 82, 846), radius=12 * SS, fill=col + (255,))
        d.rectangle(S(cx + 26, 820, cx + 74, 840), fill=(160, 190, 220, 230))
        d.ellipse(S(cx + 10, 872, cx + 32, 894), fill=(15, 15, 20, 255))
        d.ellipse(S(cx + 68, 872, cx + 90, 894), fill=(15, 15, 20, 255))

    # ground, path, trees
    ground = vgrad(CW, int(CH * 0.26), [(0, (40, 52, 60)), (1, (18, 24, 32))])
    img.paste(ground, (0, int(CH * 0.74)))
    d = ImageDraw.Draw(img, "RGBA")
    d.polygon(S(560, 900, 840, 900, 1000, 1200, 380, 1200), fill=(196, 168, 150, 255))
    d.polygon(S(560, 900, 840, 900, 860, 930, 540, 930), fill=(232, 200, 170, 255))
    for tx, ty, tr in [(120, 860, 120), (300, 880, 90), (1020, 900, 80), (1500, 940, 110), (60, 1010, 150)]:
        d.rectangle(S(tx - 8, ty, tx + 8, ty + tr * 0.9), fill=(34, 26, 24, 255))
        for k in range(5):
            ox, oy = rng.randint(-tr // 2, tr // 2), rng.randint(-tr // 2, tr // 4)
            g = rng.randint(70, 110)
            d.ellipse(S(tx + ox - tr * 0.6, ty + oy - tr * 0.8, tx + ox + tr * 0.6, ty + oy + tr * 0.4), fill=(24, g, 48, 255))
    for lx in (520, 880, 1120):
        d.rectangle(S(lx, 800, lx + 6, 930), fill=(24, 28, 40, 255))
        img = glow(img, S(lx + 3, 800), 120 * SS, (255, 200, 120), 0.7)
        d = ImageDraw.Draw(img, "RGBA")
    finish(img, "demo_visual_1.jpg")


# --------------------------------------------------------------------------
def living_room():
    rng = random.Random(21)
    img = vgrad(CW, CH, [(0, (236, 228, 216)), (1, (214, 202, 188))])
    d = ImageDraw.Draw(img, "RGBA")
    floor = vgrad(CW, int(CH * 0.3), [(0, (176, 134, 96)), (1, (120, 86, 60))])
    img.paste(floor, (0, int(CH * 0.7)))
    d = ImageDraw.Draw(img, "RGBA")
    for i in range(-10, 30):
        d.line(S(800 + i * 70, 840, 800 + i * 190 - 1500, 1200), fill=(90, 62, 42, 70), width=3)
    for k in range(6):
        y = 840 + k * k * 11
        d.line(S(0, y, 1600, y), fill=(90, 62, 42, 50), width=2)
    d.rectangle(S(0, 826, 1600, 840), fill=(246, 242, 234, 255))      # skirting

    # window
    wx0, wy0, wx1, wy1 = 1020, 130, 1500, 780
    sky = vgrad(CW, CH, [(0, (120, 170, 220)), (0.5, (250, 200, 170)), (1, (255, 226, 190))])
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rectangle(S(wx0, wy0, wx1, wy1), fill=255)
    img.paste(sky, (0, 0), mask)
    d = ImageDraw.Draw(img, "RGBA")
    x = wx0
    while x < wx1:
        w = rng.randint(40, 80)
        h = rng.randint(80, 260)
        d.rectangle(S(x, wy1 - h, min(x + w, wx1), wy1), fill=(104, 112, 150, 230))
        x += w + 4
    d.rectangle(S(wx0 - 16, wy0 - 16, wx1 + 16, wy1 + 16), outline=(60, 52, 48, 255), width=16 * SS)
    d.line(S((wx0 + wx1) / 2, wy0, (wx0 + wx1) / 2, wy1), fill=(60, 52, 48, 255), width=10 * SS)
    d.line(S(wx0, 450, wx1, 450), fill=(60, 52, 48, 255), width=8 * SS)
    for cx in (wx0 - 60, wx1 + 10):
        d.rectangle(S(cx, wy0 - 40, cx + 70, 790), fill=(244, 238, 228, 150))
    # light beams on floor
    beam = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(beam).polygon(S(1020, 790, 1500, 790, 1180, 1200, 560, 1200), fill=(255, 232, 190, 70))
    beam = beam.filter(ImageFilter.GaussianBlur(30 * SS))
    img.paste(beam, (0, 0), beam)
    d = ImageDraw.Draw(img, "RGBA")

    # wall art
    for (ax0, ay0, ax1, ay1, col) in [(230, 190, 420, 400, (58, 90, 110)), (450, 220, 580, 380, (200, 140, 90)), (610, 190, 790, 340, (96, 128, 98))]:
        d.rectangle(S(ax0 - 8, ay0 - 8, ax1 + 8, ay1 + 8), fill=(40, 34, 32, 255))
        d.rectangle(S(ax0, ay0, ax1, ay1), fill=(240, 234, 224, 255))
        d.rectangle(S(ax0 + 18, ay0 + 18, ax1 - 18, ay1 - 18), fill=col + (255,))
        d.ellipse(S((ax0 + ax1) / 2 - 24, ay0 + 40, (ax0 + ax1) / 2 + 24, ay0 + 88), fill=(255, 236, 200, 230))

    # rug
    d.rounded_rectangle(S(190, 900, 1000, 1130), radius=40 * SS, fill=(196, 170, 140, 255))
    d.rounded_rectangle(S(222, 920, 968, 1110), radius=28 * SS, fill=(66, 96, 112, 255))
    for k in range(6):
        d.line(S(250 + k * 120, 930, 250 + k * 120, 1100), fill=(228, 206, 170, 130), width=6 * SS)

    # sofa
    soft_shadow(img, S(160, 640, 960, 880), 30 * SS, 110, S(0, 30))
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle(S(170, 520, 950, 700), radius=50 * SS, fill=(86, 112, 132, 255))     # back
    d.rounded_rectangle(S(130, 610, 990, 800), radius=44 * SS, fill=(98, 126, 148, 255))     # seat
    d.rounded_rectangle(S(100, 570, 220, 810), radius=40 * SS, fill=(76, 100, 120, 255))
    d.rounded_rectangle(S(900, 570, 1020, 810), radius=40 * SS, fill=(76, 100, 120, 255))
    for k, col in enumerate([(236, 190, 120), (210, 214, 220), (190, 120, 100)]):
        d.rounded_rectangle(S(230 + k * 210, 560, 360 + k * 210, 690), radius=26 * SS, fill=col + (255,))
    for lx in (170, 900):
        d.rectangle(S(lx, 800, lx + 22, 850), fill=(52, 38, 30, 255))

    # coffee table
    soft_shadow(img, S(360, 920, 800, 1010), 20 * SS, 100, S(0, 18))
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle(S(360, 890, 800, 940), radius=14 * SS, fill=(74, 54, 42, 255))
    d.rectangle(S(390, 940, 406, 1010), fill=(52, 38, 30, 255))
    d.rectangle(S(754, 940, 770, 1010), fill=(52, 38, 30, 255))
    d.ellipse(S(520, 862, 580, 892), fill=(236, 232, 224, 255))
    d.rectangle(S(600, 870, 700, 890), fill=(184, 90, 70, 255))

    # floor lamp + plant
    d.rectangle(S(1040, 560, 1048, 960), fill=(34, 34, 40, 255))
    d.polygon(S(990, 560, 1098, 560, 1074, 470, 1014, 470), fill=(250, 228, 180, 255))
    img = glow(img, S(1044, 520), 230 * SS, (255, 210, 140), 0.55)
    d = ImageDraw.Draw(img, "RGBA")
    d.polygon(S(1380, 860, 1480, 860, 1462, 960, 1398, 960), fill=(204, 120, 84, 255))
    for k in range(9):
        ang = -1.2 + k * 0.3
        ex, ey = 1430 + np.sin(ang) * 150, 840 - np.cos(ang) * 200
        d.line(S(1430, 860, ex, ey), fill=(46, 100, 62, 255), width=5 * SS)
        d.ellipse(S(ex - 38, ey - 22, ex + 38, ey + 22), fill=(60, 128, 78, 255))
    finish(img, "demo_visual_2.jpg")


# --------------------------------------------------------------------------
def kitchen():
    rng = random.Random(31)
    img = vgrad(CW, CH, [(0, (228, 226, 222)), (1, (206, 204, 202))])
    d = ImageDraw.Draw(img, "RGBA")
    # backsplash tiles
    for ty in range(300, 700, 32):
        d.line(S(0, ty, 1600, ty), fill=(180, 178, 176, 120), width=2)
        off = 0 if (ty // 32) % 2 == 0 else 45
        for tx in range(-90 + off, 1600, 90):
            d.line(S(tx, ty, tx, ty + 32), fill=(180, 178, 176, 100), width=2)
    # window
    d.rectangle(S(640, 340, 960, 600), fill=(60, 52, 48, 255))
    sky = vgrad(CW, CH, [(0, (150, 196, 232)), (1, (255, 232, 200))])
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rectangle(S(656, 356, 944, 584), fill=255)
    img.paste(sky, (0, 0), mask)
    d = ImageDraw.Draw(img, "RGBA")
    d.line(S(800, 356, 800, 584), fill=(60, 52, 48, 255), width=8 * SS)
    # tall units + fridge
    d.rectangle(S(0, 60, 250, 1000), fill=(64, 76, 96, 255))
    d.rectangle(S(18, 80, 232, 520), fill=(72, 86, 108, 255))
    d.rectangle(S(18, 540, 232, 980), fill=(70, 82, 104, 255))
    d.rectangle(S(222, 280, 232, 360), fill=(196, 168, 110, 255))
    d.rectangle(S(1180, 60, 1600, 1000), fill=(190, 194, 202, 255))      # fridge
    d.rectangle(S(1190, 70, 1590, 560), fill=(206, 210, 218, 255))
    d.rectangle(S(1190, 576, 1590, 990), fill=(200, 204, 212, 255))
    d.rectangle(S(1210, 280, 1222, 440), fill=(120, 124, 132, 255))
    d.rectangle(S(1210, 640, 1222, 800), fill=(120, 124, 132, 255))
    # upper cabinets
    for x0 in (270, 990):
        for k in range(2):
            ux = x0 + k * 170
            d.rectangle(S(ux, 80, ux + 160, 300), fill=(66, 80, 102, 255))
            d.rectangle(S(ux + 8, 88, ux + 152, 292), fill=(74, 90, 114, 255))
            d.rectangle(S(ux + 70, 262, ux + 90, 270), fill=(196, 168, 110, 255))
    # hood
    d.polygon(S(560, 60, 1040, 60, 980, 220, 620, 220), fill=(170, 174, 182, 255))
    d.rectangle(S(700, 220, 900, 250), fill=(120, 124, 132, 255))
    # lower cabinets and counter
    d.rectangle(S(250, 700, 1180, 1010), fill=(62, 74, 94, 255))
    for k in range(5):
        cx = 270 + k * 180
        d.rectangle(S(cx, 740, cx + 168, 990), fill=(72, 86, 108, 255))
        d.rectangle(S(cx + 54, 748, cx + 114, 757), fill=(196, 168, 110, 255))
    d.rectangle(S(250, 676, 1180, 706), fill=(238, 238, 242, 255))
    d.rectangle(S(250, 706, 1180, 716), fill=(180, 182, 190, 255))
    # cooktop
    for cx in (700, 800, 900):
        d.ellipse(S(cx - 30, 660, cx + 30, 676), fill=(30, 30, 34, 255))
    # under-cabinet LED glow
    strip = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(strip).rectangle(S(270, 300, 1180, 316), fill=(255, 226, 170, 210))
    strip = strip.filter(ImageFilter.GaussianBlur(14 * SS))
    img.paste(strip, (0, 0), strip)
    # island + stools
    soft_shadow(img, S(180, 930, 1300, 1080), 30 * SS, 120, S(0, 30))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle(S(200, 860, 1280, 1150), fill=(52, 62, 80, 255))
    d.rectangle(S(170, 830, 1310, 872), fill=(244, 244, 248, 255))
    d.rectangle(S(170, 872, 1310, 882), fill=(186, 188, 196, 255))
    for k in range(6):
        d.rectangle(S(230 + k * 170, 900, 330 + k * 170, 1130), fill=(60, 72, 92, 255))
        d.rectangle(S(270 + k * 170, 996, 290 + k * 170, 1004), fill=(196, 168, 110, 255))
    for sx in (420, 700, 980):
        d.rounded_rectangle(S(sx - 70, 720, sx + 70, 760), radius=18 * SS, fill=(200, 150, 100, 255))
        d.rectangle(S(sx - 6, 760, sx + 6, 1050), fill=(30, 30, 34, 255))
        d.line(S(sx - 54, 1060, sx + 54, 1060), fill=(30, 30, 34, 255), width=8 * SS)
    d.ellipse(S(560, 790, 700, 830), fill=(230, 120, 70, 255))                 # fruit bowl
    d.ellipse(S(740, 800, 780, 830), fill=(120, 170, 70, 255))
    # pendants
    for px in (420, 700, 980):
        d.line(S(px, 0, px, 560), fill=(40, 40, 46, 255), width=3 * SS)
        d.polygon(S(px - 56, 600, px + 56, 600, px + 34, 540, px - 34, 540), fill=(30, 32, 40, 255))
        d.ellipse(S(px - 22, 592, px + 22, 616), fill=(255, 236, 190, 255))
        img = glow(img, S(px, 606), 240 * SS, (255, 214, 150), 0.5)
        d = ImageDraw.Draw(img, "RGBA")
    finish(img, "demo_visual_3.jpg")


# --------------------------------------------------------------------------
def balcony():
    rng = random.Random(41)
    img = vgrad(CW, CH, [(0, (40, 44, 104)), (0.35, (150, 90, 140)), (0.6, (244, 128, 100)), (0.78, (255, 196, 124)), (1, (255, 220, 160))])
    img = glow(img, S(1000, 700), CW * 0.5, (255, 160, 80), 0.8)
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse(S(900, 590, 1100, 790), fill=(255, 236, 190, 255))
    for layer, (col, base, hmin, hmax) in enumerate([((128, 92, 130, 150), 760, 70, 220), ((86, 64, 112, 190), 790, 90, 280), ((48, 40, 76, 235), 830, 70, 330)]):
        x = -20
        while x < 1650:
            w = rng.randint(50, 130)
            h = rng.randint(hmin, hmax)
            d.rectangle(S(x, base - h, x + w, base + 100), fill=col)
            if layer == 2:
                for wy in range(base - h + 16, base, 26):
                    for wx in range(x + 10, x + w - 10, 20):
                        if rng.random() < 0.3:
                            d.rectangle(S(wx, wy, wx + 8, wy + 12), fill=(255, 212, 140, 230))
            x += w + rng.randint(0, 12)
    # floor of balcony
    floor = vgrad(CW, int(CH * 0.2), [(0, (110, 96, 92)), (1, (66, 56, 56))])
    img.paste(floor, (0, int(CH * 0.8)))
    d = ImageDraw.Draw(img, "RGBA")
    for k in range(-6, 20):
        d.line(S(k * 120, 960, k * 120 - 120 + (k - 8) * 40, 1200), fill=(40, 34, 34, 90), width=3)
    # glass railing
    d.rectangle(S(0, 700, 1600, 720), fill=(34, 34, 40, 255))
    d.rectangle(S(0, 700, 1600, 704), fill=(120, 120, 130, 255))
    glass = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glass).rectangle(S(0, 720, 1600, 960), fill=(220, 230, 240, 38))
    img.paste(glass, (0, 0), glass)
    d = ImageDraw.Draw(img, "RGBA")
    for px in range(0, 1700, 400):
        d.rectangle(S(px, 700, px + 16, 970), fill=(34, 34, 40, 255))
    d.rectangle(S(0, 960, 1600, 986), fill=(34, 34, 40, 255))
    d.line(S(0, 740, 1600, 880), fill=(255, 255, 255, 40), width=6 * SS)
    # planters
    for px in (60, 1380):
        d.rectangle(S(px, 900, px + 180, 980), fill=(70, 56, 52, 255))
        for k in range(10):
            ang = -1.4 + k * 0.31
            ex, ey = px + 90 + np.sin(ang) * 110, 880 - np.cos(ang) * 120
            d.line(S(px + 90, 900, ex, ey), fill=(40, 96, 60, 255), width=5 * SS)
            d.ellipse(S(ex - 34, ey - 18, ex + 34, ey + 18), fill=(54, 120, 76, 255))
    # bistro set (silhouettes with warm rim)
    soft_shadow(img, S(520, 1040, 1100, 1110), 26 * SS, 120, S(0, 10))
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse(S(660, 900, 940, 940), fill=(46, 40, 44, 255))
    d.rectangle(S(794, 940, 806, 1090), fill=(46, 40, 44, 255))
    d.ellipse(S(740, 1076, 860, 1100), fill=(46, 40, 44, 255))
    d.ellipse(S(740, 892, 780, 910), fill=(255, 238, 200, 255))
    for cx, flip in ((560, 1), (1020, -1)):
        d.rounded_rectangle(S(cx - 70, 930, cx + 70, 960), radius=14 * SS, fill=(40, 34, 38, 255))
        d.rectangle(S(cx - 70 if flip == 1 else cx + 56, 820, cx - 56 if flip == 1 else cx + 70, 960), fill=(40, 34, 38, 255))
        for lx in (cx - 60, cx + 46):
            d.rectangle(S(lx, 960, lx + 14, 1080), fill=(40, 34, 38, 255))
    # string lights
    pts = [(x, 120 + 70 * np.sin((x / 1600) * np.pi * 3) ** 2) for x in range(0, 1601, 40)]
    d.line([(px * SS, py * SS) for px, py in pts], fill=(30, 28, 34, 255), width=3 * SS)
    for px, py in pts[1::2]:
        img = glow(img, S(px, py + 14), 40 * SS, (255, 220, 150), 0.9)
        d = ImageDraw.Draw(img, "RGBA")
        d.ellipse(S(px - 7, py + 8, px + 7, py + 22), fill=(255, 244, 210, 255))
    finish(img, "demo_visual_4.jpg")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    targets = {"1": exterior, "2": living_room, "3": kitchen, "4": balcony}
    wanted = sys.argv[1:] or list(targets)
    for key in wanted:
        targets[key]()
