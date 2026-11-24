"""RotN-style (dark ink, red edge, white brush letters) buttons for the game mode screen."""
import os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'extra', 'GameMode')
IMPACT = '/System/Library/Fonts/Supplemental/Impact.ttf'

def card(text, sub, w=150, h=62, s=4):
    W, H = w * s, h * s
    im = Image.new('RGBA', (W, H))
    d = ImageDraw.Draw(im)
    # ink body with a slanted cut like the RotN mode cards
    body = [(10 * s, 0), (W, 0), (W - 10 * s, H), (0, H)]
    d.polygon(body, fill=(14, 10, 10, 235))
    d.line(body + [body[0]], fill=(150, 18, 18, 255), width=3 * s)
    d.polygon([(10 * s, 0), (40 * s, 0), (30 * s, 6 * s), (8 * s, 6 * s)], fill=(190, 25, 25, 255))
    f = ImageFont.truetype(IMPACT, 30 * s)
    tw = d.textlength(text, font=f)
    glow = Image.new('RGBA', (W, H))
    gd = ImageDraw.Draw(glow)
    gd.text(((W - tw) / 2, 6 * s), text, font=f, fill=(255, 40, 40, 255))
    im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(4 * s)))
    d.text(((W - tw) / 2, 6 * s), text, font=f, fill=(240, 240, 240, 255))
    if sub:
        f2 = ImageFont.truetype(IMPACT, 10 * s)
        sw = d.textlength(sub, font=f2)
        d.text(((W - sw) / 2, 44 * s), sub, font=f2, fill=(190, 190, 190, 255))
    return im.resize((w, h), Image.LANCZOS)

def label(text, size, color, pad=6, bg=None):
    f = ImageFont.truetype(IMPACT, size * 4)
    tmp = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    tw = int(tmp.textlength(text, font=f)); th = int(size * 4 * 1.25)
    im = Image.new('RGBA', (tw + pad * 8, th + pad * 4), bg or (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((pad * 4, pad), text, font=f, fill=color)
    return im.resize((im.width // 4, im.height // 4), Image.LANCZOS)

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    card('1 VS 1', 'DUEL').save(os.path.join(OUT, 'mode_1v1.png'))
    card('2 VS 2', 'TEAM BATTLE').save(os.path.join(OUT, 'mode_2v2.png'))
    card('3 VS 3', 'CLASSIC').save(os.path.join(OUT, 'mode_3v3.png'))
    small = card('BACK', None, 150, 62).resize((72, 30), Image.LANCZOS)
    small.save(os.path.join(OUT, 'back.png'))
    label('GAME MODE', 13, (245, 245, 245, 255), 3, (0, 0, 0, 255)).save(os.path.join(OUT, 'title.png'))
    if len(sys.argv) > 1:
        prev = Image.new('RGBA', (480, 140), (90, 75, 55, 255))
        for i, n in enumerate(['mode_1v1', 'mode_2v2', 'mode_3v3']):
            im = Image.open(os.path.join(OUT, n + '.png')); prev.alpha_composite(im, (i * 158, 0))
        prev.alpha_composite(Image.open(os.path.join(OUT, 'back.png')), (10, 80))
        prev.alpha_composite(Image.open(os.path.join(OUT, 'title.png')), (150, 90))
        prev.resize((960, 280)).save(sys.argv[1])
