#!/usr/bin/env python3
"""Build the Rise of the Ninja 2.2 look on top of the NarutoSenki-V2 resources.

Writes v2app/overlay/, which build.sh copies over the V2 Resources:
  - plain RotN images (title logo, backgrounds, Touch start button, hidden menu bars)
  - merged sprite atlases: RotN frames replace V2 frames of the same name, V2-only frames are kept
Usage: python3 rotn_assets.py
"""
import glob, os, plistlib, re, shutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
import rotn_skin
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROTN = os.environ.get('ROTN_ASSETS') or os.path.join(HERE, '..', 'assets')
V2 = os.path.join(HERE, '..', 'engine', 'projects', 'NarutoSenki', 'Resources')
OUT = os.path.join(HERE, 'overlay')

PLAIN = ['logo.png', 'red_bg.png', 'blue_bg.png', 'push_start.png', 'menu_bar2.png', 'menu_bar3.png']
ATLASES = {'Menu': 'Menu.(exa)'}          # atlas name -> RotN texture file


def nums(s):
    return [int(round(float(v))) for v in re.findall(r'-?[\d.]+', s)]


def frames(plist_path, tex_path):
    d = plistlib.load(open(plist_path, 'rb'))
    tex = Image.open(tex_path).convert('RGBA')
    res = {}
    for name, f in d['frames'].items():
        x, y, w, h = nums(f.get('frame') or f['textureRect'])
        rot = f.get('rotated', f.get('textureRotated', False))
        if w <= 0 or h <= 0:
            img = Image.new('RGBA', (1, 1))
            f = dict(f, offset='{0,0}', sourceColorRect='{{0,0},{1,1}}', sourceSize='{1,1}')
        elif rot:
            img = tex.crop((x, y, x + h, y + w)).rotate(90, expand=True)
        else:
            img = tex.crop((x, y, x + w, y + h))
        res[name] = (img, f)
    return res


def pack(items, max_w=2048):
    order = sorted(items, key=lambda n: -items[n][0].height)
    x = y = row_h = 0
    pos = {}
    for n in order:
        img = items[n][0]
        if x + img.width + 2 > max_w:
            x, y, row_h = 0, y + row_h + 2, 0
        pos[n] = (x, y)
        x += img.width + 2
        row_h = max(row_h, img.height)
    W = max_w
    H = 1
    while H < y + row_h: H *= 2
    tex = Image.new('RGBA', (W, H))
    for n, (px, py) in pos.items():
        tex.paste(items[n][0], (px, py))
    return tex, pos


def write_atlas(name, items):
    tex, pos = pack(items)
    fr = {}
    for n, (img, f) in items.items():
        px, py = pos[n]
        fr[n] = {
            'frame': '{{%d,%d},{%d,%d}}' % (px, py, img.width, img.height),
            'offset': f.get('offset', '{0,0}'),
            'rotated': False,
            'sourceColorRect': f.get('sourceColorRect', '{{0,0},{%d,%d}}' % (img.width, img.height)),
            'sourceSize': f.get('sourceSize', '{%d,%d}' % (img.width, img.height)),
        }
    tex.save(os.path.join(OUT, name + '.png'), optimize=True)
    meta = {'format': 2, 'realTextureFileName': name + '.png', 'textureFileName': name + '.png',
            'size': '{%d,%d}' % tex.size}
    plistlib.dump({'frames': fr, 'metadata': meta}, open(os.path.join(OUT, name + '.plist'), 'wb'))
    return tex


def online_caption(card):
    """Online Battle card: 'Sorry this mode not available !' -> the Wi-Fi battle caption."""
    from PIL import ImageDraw, ImageFont
    card = card.copy()
    d = ImageDraw.Draw(card)
    # the caption sits on the dark strip at the bottom-left
    bg = card.getpixel((4, 307))
    f = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 13)
    old_w = 215  # width of the original caption
    new_w = int(d.textlength("Do'stlar bilan Wi-Fi orqali jang !", font=f))
    d.rectangle((8, 296, 14 + max(old_w, new_w) + 4, 318), fill=bg)
    d.text((14, 299), "Do'stlar bilan Wi-Fi orqali jang !", font=f, fill=(230, 230, 230, 255))
    return card


def silhouette(half_img, name):
    """RotN-style shadow for heroes RotN has no picture of: a black figure with the name on a brush stroke."""
    from PIL import ImageDraw, ImageFont, ImageFilter
    W, H = 304, 315
    canvas = Image.new('RGBA', (W, H))
    fig = half_img.copy()
    k = min(260 / fig.width, 300 / fig.height)
    fig = fig.resize((max(1, int(fig.width * k)), max(1, int(fig.height * k))), Image.LANCZOS)
    a = fig.split()[3].point(lambda v: 255 if v > 200 else 0)  # glow/aura is not part of the figure
    # V2 portraits are cut off at the bottom: let the figure melt into the ink instead of ending in a
    # hard edge
    from PIL import ImageChops
    fade = Image.new('L', fig.size, 255)
    fd = ImageDraw.Draw(fade)
    top = H - fig.height  # canvas y of the figure's first row
    y0, y1 = 165 - top, 238 - top  # fully gone at the name stroke
    for y in range(max(0, y0), fig.height):
        v = 0 if y >= y1 else int(255 * (1 - (y - y0) / max(1, y1 - y0)) ** 1.4)
        fd.line([(0, y), (fig.width, y)], fill=v)
    # where the portrait was cut off at the left/right border, the figure fades out (only there)
    cut = Image.new('L', fig.size, 0)
    for x in (0, fig.width - 1):
        col = a.crop((x, 0, x + 1, fig.height))
        cut.paste(col, (x, 0))
    if cut.getbbox():
        glow = cut.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(16))
        m = max(1, glow.getextrema()[1])
        fade = ImageChops.multiply(fade, glow.point(lambda v: max(0, 255 - min(255, v * 255 * 1.6 / m))))
    a = ImageChops.multiply(a, fade).filter(ImageFilter.GaussianBlur(0.8))
    black = Image.new('RGBA', fig.size, (8, 8, 10, 255))
    black.putalpha(a)
    canvas.alpha_composite(black, ((W - fig.width) // 2, H - fig.height))
    d = ImageDraw.Draw(canvas)
    # ink brush stroke + name, like the RotN pictures
    sys.path.insert(0, os.path.join(HERE, 'tools'))
    from cancel_btn import brush_stroke
    stroke = brush_stroke(W, 46, (0, 0, 0, 240), seed=len(name))
    canvas.alpha_composite(stroke, (0, 212))
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Impact.ttf', 22)
    text = name.upper()
    gap = 1.5
    tw = sum(d.textlength(ch, font=font) for ch in text) + gap * (len(text) - 1)
    x = (W - tw) / 2
    for ch in text:  # letter-spaced like the RotN names
        d.text((x, 225), ch, font=font, fill=(170, 170, 170, 255))
        x += d.textlength(ch, font=font) + gap
    return canvas


def card_from(v2_card):
    """RotN-style 29x66 card from a V2 select card (centre crop, no squashing, dark frame)."""
    from PIL import ImageDraw
    w, h = v2_card.size
    cw = max(1, round(h * 29 / 66))
    x0 = max(0, (w - cw) // 2)
    c = v2_card.crop((x0, 0, x0 + cw, h)).resize((29, 66), Image.LANCZOS)
    d = ImageDraw.Draw(c)
    d.rectangle((0, 0, 28, 65), outline=(18, 18, 18, 255), width=2)
    d.rectangle((2, 2, 26, 63), outline=(70, 70, 70, 255), width=1)
    return c


def card_from_portrait(img):
    """Card for heroes without a V2 card (the playable forms): the face area of their big portrait."""
    bbox = img.getbbox() or (0, 0, img.width, img.height)
    img = img.crop(bbox)
    cw = img.width * 0.42
    ch = cw * 66 / 29
    x0 = (img.width - cw) / 2
    face = img.crop((int(x0), 0, int(x0 + cw), int(min(ch, img.height))))
    bg = Image.new('RGBA', face.size, (40, 34, 30, 255))
    bg.alpha_composite(face)
    return card_from(bg)


# RotN's own pictures are only right for these heroes; for the others RotN showed somebody else
ROTN_CORRECT = {'Naruto', 'Sasuke', 'Kakashi', 'Itachi', 'Kisame', 'Deidara', 'Minato', 'Tobirama', 'Hiruzen'}
FULL_NAMES = {
    'Asuma': 'Sarutobi Asuma', 'Chiyo': 'Chiyo', 'Choji': 'Akimichi Choji', 'Gaara': 'Gaara', 'Hidan': 'Hidan',
    'Hinata': 'Hyuga Hinata', 'Ino': 'Yamanaka Ino', 'Jiraiya': 'Jiraiya', 'Jugo': 'Jugo', 'Kakuzu': 'Kakuzu',
    'Kankuro': 'Kankuro', 'Karin': 'Uzumaki Karin', 'Kiba': 'Inuzuka Kiba', 'Kimimaro': 'Kaguya Kimimaro',
    'Konan': 'Konan', 'Lee': 'Rock Lee', 'Neji': 'Hyuga Neji', 'Orochimaru': 'Orochimaru', 'Pain': 'Pain',
    'Sai': 'Sai', 'Sakura': 'Haruno Sakura', 'Shikamaru': 'Nara Shikamaru', 'Shino': 'Aburame Shino',
    'Suigetsu': 'Hozuki Suigetsu', 'Tenten': 'Tenten', 'Tobi': 'Tobi', 'Tsunade': 'Tsunade',
    # playable forms (RotN 2.2)
    'SageNaruto': 'Naruto (Sage)', 'RikudoNaruto': 'Naruto (Rikudo)', 'Nagato': 'Uzumaki Nagato',
    'ImmortalSasuke': 'Sasuke (Immortal)', 'SageJiraiya': 'Jiraiya (Sage)',
}
FORMS = ['SageNaruto', 'RikudoNaruto', 'Nagato', 'ImmortalSasuke', 'SageJiraiya']


def select_extras():
    """Adds RotN select-screen pictures to the Select atlas: <hero>_shadow.png, <hero>_rcard.png, rotn_skill/start,
    and the missing pictures of the playable forms."""
    import atlas
    src = os.path.join(OUT, 'Select.plist') if os.path.exists(os.path.join(OUT, 'Select.plist')) else os.path.join(V2, 'Select.plist')
    items = atlas.load_frames(src, atlas.texture_path(src))
    v2sel = atlas.load_frames(os.path.join(V2, 'Select.plist'))
    v2ui = atlas.load_frames(os.path.join(V2, 'UI.plist'))
    v2rec = atlas.load_frames(os.path.join(V2, 'Record.plist'))
    rotn = atlas.load_frames(os.path.join(ROTN, 'Select.plist'), atlas.texture_path(os.path.join(ROTN, 'Select.plist')))
    full = lambda img: {'offset': '{0,0}', 'sourceColorRect': '{{0,0},{%d,%d}}' % img.size, 'sourceSize': '{%d,%d}' % img.size}
    heroes = [k[:-11] for k in v2sel if k.endswith('_select.png')] + FORMS

    def portrait(h):
        for atl, key in ((v2sel, h + '_half.png'), (v2rec, h + '_full.png')):
            if key in atl and atl[key][0].getbbox():
                return atl[key][0]
        return None

    for h in heroes:
        if h in ROTN_CORRECT and h + '_font.png' in rotn and rotn[h + '_font.png'][0].width > 100:
            shadow = rotn[h + '_font.png'][0]
            card = card_from(v2sel[h + '_select.png'][0])  # same card style for everybody
        else:
            pic = portrait(h)
            if pic is None:
                continue
            shadow = silhouette(pic, FULL_NAMES.get(h, h))
            card = card_from(v2sel[h + '_select.png'][0]) if h + '_select.png' in v2sel else card_from_portrait(pic)
        items[h + '_shadow.png'] = (shadow, full(shadow))
        items[h + '_rcard.png'] = (card, full(card))
        if h in FORMS:
            if h + '_select.png' not in items:
                items[h + '_select.png'] = (card, full(card))
            if h + '_small.png' not in items and h + '_avator.png' in v2ui:
                av = v2ui[h + '_avator.png'][0]
                sm = av.resize((32, max(1, round(av.height * 32 / av.width))), Image.LANCZOS)
                items[h + '_small.png'] = (sm, full(sm))
            if h + '_font.png' not in items:
                dot = Image.new('RGBA', (1, 1))
                items[h + '_font.png'] = (dot, full(dot))
    # RotN's extra heroes (fight with the slot hero's skills, look like the RotN character)
    import rotn_heroes
    rec_full = atlas.load_frames(os.path.join(OUT, 'Record.plist'), os.path.join(OUT, 'Record.png'))
    for skin, (slot, title) in rotn_heroes.SKINS.items():
        rc = rotn.get(slot + '_select.png')
        if slot + '_font.png' in rotn and rotn[slot + '_font.png'][0].width >= 100:
            shadow = rotn[slot + '_font.png'][0]
            card = card_from(rc[0]) if rc and rc[0].width > 10 else card_from_portrait(shadow)
        else:
            # RotN has no select pictures for this hero: build them from its big RotN portrait
            pic = rec_full.get(skin + '_full.png')
            if pic is None or not pic[0].getbbox():
                print('no pictures for', skin)
                continue
            shadow = silhouette(pic[0], title)
            card = card_from_portrait(pic[0])
        items[skin + '_shadow.png'] = (shadow, full(shadow))
        items[skin + '_rcard.png'] = (card, full(card))
        items[skin + '_select.png'] = (card, full(card))
        dot = Image.new('RGBA', (1, 1))
        items[skin + '_font.png'] = (dot, full(dot))
        if skin + '_small.png' not in items:
            av = items.get(skin + '_avator.png') or None
            src = av[0] if av else card
            sm = src.resize((32, max(1, round(src.height * 32 / src.width))), Image.LANCZOS)
            items[skin + '_small.png'] = (sm, full(sm))
        if skin + '_half.png' not in items:
            # result screen picture: the RotN big portrait if any, else the shadow
            items[skin + '_half.png'] = (shadow, full(shadow))
    for n in ('skill_btn.png', 'start_btn.png', 'tip1.png', 'tip2.png', 'tip3.png'):
        img = rotn[n][0]
        items['rotn_' + n] = (img, full(img))
    # "Bekor" (undo the last pick), drawn in the style of RotN's captions at 3x (scaled down in Lua)
    sys.path.insert(0, os.path.join(HERE, 'tools'))
    from cancel_btn import cancel_button
    img = cancel_button()
    items['rotn_cancel_btn.png'] = (img, full(img))
    atlas.write_atlas(OUT, 'Select', items)
    print('select extras:', len(heroes), 'heroes')


def main():
    stamp = os.path.join(OUT, '.stamp')
    srcs = [__file__] + glob.glob(os.path.join(HERE, 'tools', '*.py'))
    if os.path.exists(stamp) and all(os.path.getmtime(f) < os.path.getmtime(stamp) for f in srcs):
        print('overlay up to date'); return
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    for f in PLAIN:
        shutil.copy(os.path.join(ROTN, f), os.path.join(OUT, f))
    for name, rotn_tex in ATLASES.items():
        items = frames(os.path.join(V2, name + '.plist'), os.path.join(V2, name + '.png'))
        rotn = frames(os.path.join(ROTN, name + '.plist'), os.path.join(ROTN, rotn_tex))
        items.update(rotn)
        if name == 'Menu' and 'menu01_text.png' in items:
            img, f = items['menu01_text.png']
            items['menu01_text.png'] = (online_caption(img), f)
        write_atlas(name, items)
        print(name, len(items), 'frames')
    log = rotn_skin.run(ROTN, V2, OUT)
    select_extras()
    open(os.path.join(OUT, '..', 'skin.log'), 'w').write('\n'.join(log) + '\n')
    print('skin:', len(log), 'items (see v2app/skin.log)')


if __name__ == '__main__':
    main()
    open(os.path.join(OUT, '.stamp'), 'w').close()
