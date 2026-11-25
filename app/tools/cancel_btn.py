"""RotN 2.2 select screen: the "Bekor" (undo pick) button, drawn like RotN's black "Start"/"Skill"
captions with a red ink brush stroke behind (3x resolution, shown at 1/3 scale)."""
import math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

IMPACT = '/System/Library/Fonts/Supplemental/Impact.ttf'


def brush_stroke(w, h, color, seed=7):
    """An ink brush swoosh: thick in the middle, ragged ends, a few dry-brush gaps."""
    rnd = random.Random(seed)
    img = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(img)
    cy = h * 0.55
    for i in range(w):
        t = i / (w - 1)
        th = h * 0.62 * math.sin(math.pi * min(1, t * 1.08)) ** 0.45 + rnd.uniform(-1.5, 1.5)
        y = cy + (t - 0.5) * h * -0.18 + rnd.uniform(-0.6, 0.6)
        if th > 1:
            d.line([(i, y - th / 2), (i, y + th / 2)], fill=color)
    # dry-brush streaks
    for _ in range(9):
        y = cy + rnd.uniform(-h * 0.17, h * 0.17)
        x0 = rnd.uniform(w * 0.45, w * 0.8)
        d.line([(x0, y), (w, y + rnd.uniform(-2, 2))], fill=(0, 0, 0, 0), width=rnd.choice([1, 2]))
    # splash dots at the tail
    for _ in range(6):
        x, y = rnd.uniform(w * 0.9, w), cy + rnd.uniform(-h * 0.3, h * 0.3)
        r = rnd.uniform(1, 3)
        d.ellipse([x - r, y - r, x + r, y + r], fill=color)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def caption(text, size):
    """'Bekor' -> big first letter + small caps, like RotN's 'Start'."""
    big = ImageFont.truetype(IMPACT, size)
    small = ImageFont.truetype(IMPACT, int(size * 0.78))
    parts = [(text[0].upper(), big)] + [(c.upper(), small) for c in text[1:]]
    widths = [f.getbbox(c)[2] + 1 for c, f in parts]
    w, h = sum(widths) + 10, int(size * 1.25)
    img = Image.new('RGBA', (w, h))
    d = ImageDraw.Draw(img)
    x = 4
    for (c, f), cw in zip(parts, widths):
        y = h - 4 - f.getbbox(c)[3]
        # thin light outline so the black letters stay readable on dark ink
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, 2), (-2, 2), (2, -2)):
            d.text((x + ox, y + oy), c, font=f, fill=(240, 222, 186, 255))
        d.text((x, y), c, font=f, fill=(12, 10, 8, 255))
        x += cw
    return img


def cancel_button(text='Bekor', scale=3):
    cap = caption(text, 26 * scale)
    w, h = cap.width + 34 * scale, cap.height + 4 * scale
    out = Image.new('RGBA', (w, h))
    stroke = brush_stroke(w, int(h * 0.95), (176, 28, 24, 235))
    out.alpha_composite(stroke, (0, int(h * 0.06)))
    out.alpha_composite(cap, ((w - cap.width) // 2 - 2 * scale, (h - cap.height) // 2))
    return out


if __name__ == '__main__':
    import sys
    cancel_button().save(sys.argv[1])
