"""Sprite atlas helpers: load cocos2d plist atlases (PNG or PVRv2 .pvr.ccz) into frames, pack frames back."""
import plistlib, re, struct, zlib, os
from PIL import Image

def load_texture(path):
    if path.endswith('.pvr.ccz') or path.endswith('.pvr'):
        b = open(path, 'rb').read()
        if b[:4] == b'CCZ!': b = zlib.decompress(b[16:])
        hdr = struct.unpack('<13I', b[:52])
        h, w, flags = hdr[1], hdr[2], hdr[4]
        data = b[hdr[0]:hdr[0] + hdr[5]]
        pt = flags & 0xff
        if pt == 0x12:   # RGBA8888
            return Image.frombytes('RGBA', (w, h), data[:w * h * 4])
        if pt == 0x10:   # RGBA4444, little-endian 16-bit: byte0 = B<<4|A, byte1 = R<<4|G
            la = Image.frombytes('LA', (w, h), data[:w * h * 2])
            lo, hi = la.split()
            hiN = lambda c: c.point(lambda v: (v >> 4) * 17)
            loN = lambda c: c.point(lambda v: (v & 15) * 17)
            return Image.merge('RGBA', (hiN(hi), loN(hi), hiN(lo), loN(lo)))
        raise ValueError('pvr pixel type %x' % pt)
    return Image.open(path).convert('RGBA')

def nums(s):
    return [int(round(float(v))) for v in re.findall(r'-?[\d.]+', s)]

def texture_path(plist_path):
    """Texture named in the plist, else a non-plist/xml file with the same stem; None if missing."""
    try:
        m = plistlib.load(open(plist_path, 'rb')).get('metadata', {})
    except Exception:
        m = {}
    d = os.path.dirname(plist_path)
    name = m.get('realTextureFileName') or m.get('textureFileName')
    if name and os.path.exists(os.path.join(d, name)):
        return os.path.join(d, name)
    stem = os.path.basename(plist_path)[:-6]
    for f in sorted(os.listdir(d)):
        if f.startswith(stem + '.') and not f.endswith(('.plist', '.xml')) and f[len(stem) + 1:].count('.') <= 1:
            return os.path.join(d, f)
    return None

def load_frames(plist_path, tex_path=None):
    raw = open(plist_path, 'rb').read()
    if not raw.lstrip().startswith(b'<?xml'):  # some V2 atlases have no xml header
        raw = b'<?xml version="1.0" encoding="UTF-8"?>\n' + raw
    d = plistlib.loads(raw)
    tex = load_texture(tex_path or texture_path(plist_path))
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

def _pack(items, max_w):
    order = sorted(items, key=lambda n: (-items[n][0].height, n))
    x = y = row_h = 0
    pos = {}
    for n in order:
        img = items[n][0]
        if x + img.width + 2 > max_w:
            x, y, row_h = 0, y + row_h + 2, 0
        pos[n] = (x, y)
        x += img.width + 2
        row_h = max(row_h, img.height)
    H = 1
    while H < y + row_h: H *= 2
    return pos, H

def write_atlas(out_dir, name, items, max_w=2048):
    """Writes name.png + name.plist (format 2, unrotated); returns texture size."""
    widest = max(i[0].width for i in items.values()) + 2
    while max_w < widest: max_w *= 2
    pos, H = _pack(items, max_w)
    while H > max_w and max_w < 4096:           # keep it roughly square, max 4096
        max_w *= 2; pos, H = _pack(items, max_w)
    tex = Image.new('RGBA', (max_w, H))
    fr = {}
    for n, (img, f) in items.items():
        px, py = pos[n]
        tex.paste(img, (px, py))
        fr[n] = {
            'frame': '{{%d,%d},{%d,%d}}' % (px, py, img.width, img.height),
            'offset': f.get('offset', '{0,0}'),
            'rotated': False,
            'sourceColorRect': f.get('sourceColorRect', '{{0,0},{%d,%d}}' % (img.width, img.height)),
            'sourceSize': f.get('sourceSize', '{%d,%d}' % (img.width, img.height)),
        }
    os.makedirs(out_dir, exist_ok=True)
    tex.save(os.path.join(out_dir, name + '.png'), optimize=True)
    meta = {'format': 2, 'realTextureFileName': name + '.png', 'textureFileName': name + '.png',
            'size': '{%d,%d}' % tex.size}
    plistlib.dump({'frames': fr, 'metadata': meta}, open(os.path.join(out_dir, name + '.plist'), 'wb'))
    return tex.size

# ---- PVRv2 (.pvr.ccz) writing, premultiplied alpha like the V2 originals ----
from PIL import ImageChops

def premultiply(img):
    r, g, b, a = img.split()
    return Image.merge('RGBA', (ImageChops.multiply(r, a), ImageChops.multiply(g, a), ImageChops.multiply(b, a), a))

def pvr_header_of(path):
    b = open(path, 'rb').read()
    if b[:4] == b'CCZ!': b = zlib.decompress(b[16:])
    return list(struct.unpack('<13I', b[:52]))

def save_pvr_ccz(img, path, template_hdr):
    """img must already be premultiplied. Pixel format taken from the template header (4444 or 8888)."""
    w, h = img.size
    pt = template_hdr[4] & 0xff
    if pt == 0x12:
        data = img.tobytes()
    else:   # RGBA4444: byte0 = B<<4|A, byte1 = R<<4|G
        r, g, b, a = img.split()
        hi4 = lambda c: c.point(lambda v: (v >> 4) << 4)
        lo4 = lambda c: c.point(lambda v: v >> 4)
        lo = ImageChops.add(hi4(b), lo4(a))
        hi = ImageChops.add(hi4(r), lo4(g))
        data = Image.merge('LA', (lo, hi)).tobytes()
    hdr = list(template_hdr)
    hdr[1], hdr[2], hdr[3], hdr[5] = h, w, 0, len(data)
    raw = struct.pack('<13I', *hdr) + data
    with open(path, 'wb') as f:
        f.write(b'CCZ!' + struct.pack('>HHII', 0, 1, 0, len(raw)) + zlib.compress(raw, 9))

def pack_items(items, max_w=2048):
    widest = max(i[0].width for i in items.values()) + 2
    while max_w < widest: max_w *= 2
    pos, H = _pack(items, max_w)
    while H > max_w and max_w < 4096:
        max_w *= 2; pos, H = _pack(items, max_w)
    tex = Image.new('RGBA', (max_w, H))
    fr = {}
    for n, (img, f) in items.items():
        px, py = pos[n]
        tex.paste(img, (px, py))
        fr[n] = {
            'frame': '{{%d,%d},{%d,%d}}' % (px, py, img.width, img.height),
            'offset': f.get('offset', '{0,0}'),
            'rotated': False,
            'sourceColorRect': f.get('sourceColorRect', '{{0,0},{%d,%d}}' % (img.width, img.height)),
            'sourceSize': f.get('sourceSize', '{%d,%d}' % (img.width, img.height)),
        }
    return tex, fr

def write_plist(path, fr, tex_name, size):
    meta = {'format': 2, 'realTextureFileName': tex_name, 'textureFileName': tex_name, 'size': '{%d,%d}' % size}
    plistlib.dump({'frames': fr, 'metadata': meta}, open(path, 'wb'))
