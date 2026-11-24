"""Put Rise of the Ninja art onto the V2 resources (only where both games have the item).

- Hero/unit sprites (Unit/**/Name.plist + Name.xml): every xml action that RotN also has gets RotN's
  frames. V2's events (attack boxes, sounds, commands...) are kept and spread proportionally over the
  new frames, so V2 game logic keeps working. Units without a RotN texture (e.g. Lee) stay V2.
- Skill effect atlases (Name_Skill.plist): frame groups with the same frame count are replaced 1:1.
- UI atlases (UI, Result, Report, Record, Select, Ougis, Map, Effects/...): frames are replaced by name.
- Map pictures: replaced when the RotN file has the same size.
Writes into an output folder laid out like V2 Resources.
"""
import os, re, glob, sys
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas import load_frames, texture_path, premultiply, pvr_header_of, save_pvr_ccz, pack_items, write_plist
from PIL import Image
import rotn_heroes

# pictures taken from RotN even though their size differs (menus re-centre them)
FORCE = {'bgm_on.png', 'bgm_off.png', 'voice_on.png', 'voice_off.png'}
UI_ATLASES = ['UI', 'Result', 'Report', 'Record', 'Record2', 'Select', 'Ougis', 'Ougis2', 'Map',
              'Effects/DamageEffect', 'Effects/Shadows', 'Effects/SkillEffect']
MAP_PICS = {'Maps/map_bg1.png': 'Tiles/map_bg1.png', 'Maps/map_bg2.png': 'Tiles/map_bg2.png',
            'Maps/map_bg3.png': 'Tiles/map_bg3.png'}


def norm(name):
    """'Naruto_Idle_01.png' -> ('naruto_idle', 1); None if no numeric suffix."""
    n = name[:-4] if name.endswith('.png') else name
    m = re.match(r'(.+?)_?(\d+)$', n)
    return (m.group(1).lower().rstrip('_'), int(m.group(2))) if m else None


def size_of(f):
    from atlas import nums
    if 'sourceSize' in f: return tuple(nums(f['sourceSize']))
    x, y, w, h = nums(f.get('frame') or f['textureRect'])
    return (w, h)


def fit_to(img, f, size):
    """Untrim a RotN frame and scale it (keeping proportions, centred) onto a V2 canvas of `size`.
    None when the shapes differ too much (RotN lays that picture out differently)."""
    from atlas import nums
    rw, rh = size_of(f)
    vw, vh = size
    if min(rw, rh, vw, vh) <= 0: return None
    ra, va = rw / rh, vw / vh
    if max(ra, va) / min(ra, va) > 1.2: return None
    canvas = Image.new('RGBA', (rw, rh))
    x, y = nums(f['sourceColorRect'])[:2] if 'sourceColorRect' in f else (0, 0)
    canvas.paste(img, (x, y))
    k = min(vw / rw, vh / rh)
    sw, sh = max(1, round(rw * k)), max(1, round(rh * k))
    out = Image.new('RGBA', (vw, vh))
    out.paste(canvas.resize((sw, sh), Image.LANCZOS), ((vw - sw) // 2, (vh - sh) // 2))
    return out, {'offset': '{0,0}', 'sourceColorRect': '{{0,0},{%d,%d}}' % (vw, vh), 'sourceSize': '{%d,%d}' % (vw, vh)}


def groups(frames):
    g = {}
    for n in frames:
        k = norm(n)
        if k: g.setdefault(k[0], []).append((k[1], n))
    return {k: [n for _, n in sorted(v)] for k, v in g.items()}


def rotn_actions(xml_path):
    """RotN xml: <action value=..><frame><frameName>..</frameName>... -> {action_lower: [frame names]}"""
    txt = open(xml_path, encoding='utf-8', errors='replace').read()
    res = {}
    for m in re.finditer(r'<action\s+value="([^"]+)"(.*?)</action>', txt, re.S):
        fr = re.findall(r'<frameName>\s*([^<\s]+)\s*</frameName>', m.group(2))
        if fr: res[m.group(1).lower()] = fr
    return res


def save_atlas(out_dir, rel_base, items, v2_tex):
    """Write atlas using V2's original texture kind (pvr.ccz premultiplied, or png)."""
    os.makedirs(os.path.join(out_dir, os.path.dirname(rel_base)), exist_ok=True)
    tex, fr = pack_items(items)
    base = os.path.join(out_dir, rel_base)
    if v2_tex.endswith('.pvr.ccz'):
        name = os.path.basename(rel_base) + '.pvr.ccz'
        save_pvr_ccz(tex, base + '.pvr.ccz', pvr_header_of(v2_tex))
    else:
        name = os.path.basename(rel_base) + '.png'
        tex.save(base + '.png', optimize=True)
    write_plist(base + '.plist', fr, name, tex.size)


def skin_unit(v2_plist, rotn_plist, v2_res, out_dir, log):
    v2_tex, r_tex = texture_path(v2_plist), texture_path(rotn_plist)
    v2_xml, r_xml = v2_plist[:-6] + '.xml', rotn_plist[:-6] + '.xml'
    if not r_tex or not v2_tex or not os.path.exists(v2_xml) or not os.path.exists(r_xml):
        log.append('skip (missing RotN texture/xml): ' + os.path.basename(v2_plist)); return
    items = load_frames(v2_plist, v2_tex)
    pvr = v2_tex.endswith('.pvr.ccz')
    rframes = load_frames(rotn_plist, r_tex)
    ract = rotn_actions(r_xml)
    unit = os.path.basename(v2_plist)[:-6]
    tree = ET.parse(v2_xml)
    changed = 0
    for action in tree.getroot().iter('action'):
        aname = (action.get('name') or '').lower()
        frame_el = action.find('frame')
        if frame_el is None or aname not in ract: continue
        kids = list(frame_el)
        nv = sum(1 for k in kids if k.tag == 'f')
        rlist = [n for n in ract[aname] if n in rframes]
        if nv == 0 or not rlist: continue
        nr = len(rlist)
        # events keyed by how many V2 frames came before them
        events, seen = [], 0
        for k in kids:
            if k.tag == 'f': seen += 1
            else: events.append((seen, k))
        new = []
        ei = 0
        for j in range(nr + 1):
            while ei < len(events) and (min(nr, round(events[ei][0] * nr / nv)) if events[ei][0] == 0 else max(1, min(nr, round(events[ei][0] * nr / nv)))) == j:
                new.append(events[ei][1]); ei += 1
            if j < nr:
                fname = '%s_R_%s_%02d' % (unit, aname, j + 1)
                if fname not in items:
                    img, f = rframes[rlist[j]]
                    items[fname] = (premultiply(img) if pvr else img, f)
                el = ET.Element('f'); el.text = fname
                new.append(el)
        for k in kids: frame_el.remove(k)
        for k in new: frame_el.append(k)
        changed += 1
    if not changed:
        log.append('no matching actions: ' + unit); return
    # loading screen walks with "<unit>_Walk_NN": keep those names but show RotN art when counts match
    wv = sorted(n for n in items if re.match(re.escape(unit) + r'_Walk_\d+$', n))
    wr = [n for n in ract.get('walk', []) if n in rframes]
    if wv and len(wv) == len(wr):
        for a, b in zip(wv, wr):
            img, _ = rframes[b]
            items[a] = (premultiply(img) if pvr else img, rframes[b][1])
    rel = os.path.relpath(v2_plist, v2_res)[:-6]
    save_atlas(out_dir, rel, items, v2_tex)
    tree.write(os.path.join(out_dir, rel + '.xml'), encoding='utf-8', xml_declaration=True)
    log.append('unit %s: %d actions' % (unit, changed))


def skin_by_groups(v2_plist, rotn_plist, v2_res, out_dir, log, by_name=False, extra=None):
    v2_tex, r_tex = texture_path(v2_plist), texture_path(rotn_plist)
    if not r_tex or not v2_tex:
        log.append('skip (missing texture): ' + os.path.basename(v2_plist)); return
    items = load_frames(v2_plist, v2_tex)
    rframes = load_frames(rotn_plist, r_tex)
    pvr = v2_tex.endswith('.pvr.ccz')
    fix = (lambda i: premultiply(i)) if pvr else (lambda i: i)
    n = skipped = 0
    if by_name:
        rmap = {(k[:-4] if k.endswith('.png') else k).lower(): k for k in rframes}
        for name in list(items):
            key = (name[:-4] if name.endswith('.png') else name).lower()
            if name.split('_')[0] in rotn_heroes.RESKINNED:
                continue  # RotN shows another hero there: keep V2's picture
            if key in rmap:
                img, f = rframes[rmap[key]]
                # same canvas size only: a different canvas means RotN lays the picture out differently
                vs, rs = size_of(items[name][1]), size_of(f)
                if vs != rs and name not in FORCE:
                    fitted = fit_to(img, f, vs)
                    if fitted is None: skipped += 1; continue
                    img, f = fitted
                items[name] = (fix(img), f); n += 1
    else:
        gv, gr = groups(items), groups(rframes)
        for g, names in gv.items():
            if g in gr and len(gr[g]) == len(names):
                for a, b in zip(names, gr[g]):
                    img, f = rframes[b]
                    items[a] = (fix(img), f); n += 1
    for k, (img, f) in (extra or {}).items():
        # new heroes: RotN picture, sized like the slot hero's V2 picture so menus lay it out the same
        slot = rotn_heroes.SKINS[k.split('_')[0]][0]
        base = items.get(slot + k[len(k.split('_')[0]):])
        if base is not None and size_of(base[1]) != size_of(f):
            fitted = fit_to(img, f, size_of(base[1]))
            if fitted is not None:
                img, f = fitted
        items[k] = (fix(img), f); n += 1
    if not n:
        log.append('nothing shared: ' + os.path.basename(v2_plist)); return
    save_atlas(out_dir, os.path.relpath(v2_plist, v2_res)[:-6], items, v2_tex)
    log.append('%s: %d frames (%d kept V2: other layout)' % (os.path.relpath(v2_plist, v2_res), n, skipped))


def run(rotn, v2_res, out_dir):
    log = []
    unit_plists = {os.path.basename(p): p for p in glob.glob(os.path.join(v2_res, 'Unit', '**', '*.plist'), recursive=True)}
    for rp in sorted(glob.glob(os.path.join(rotn, 'Element', '**', '*.plist'), recursive=True)):
        base = os.path.basename(rp)
        if base not in unit_plists: continue
        stem = base[:-6].replace('_Skill', '')
        if stem in rotn_heroes.RESKINNED:
            log.append('kept V2 (RotN shows another hero): ' + base)
            continue
        try:
            if base.endswith('_Skill.plist'):
                skin_by_groups(unit_plists[base], rp, v2_res, out_dir, log)
            else:
                skin_unit(unit_plists[base], rp, v2_res, out_dir, log)
        except Exception as e:
            log.append('ERROR %s: %s' % (base, e))
    extra = rotn_heroes.ui_frames(rotn, v2_res)
    for a in UI_ATLASES:
        vp, rp = os.path.join(v2_res, a + '.plist'), os.path.join(rotn, a + '.plist')
        if os.path.exists(vp) and os.path.exists(rp):
            try: skin_by_groups(vp, rp, v2_res, out_dir, log, by_name=True, extra=extra.get(a))
            except Exception as e: log.append('ERROR %s: %s' % (a, e))
    for dst, src in MAP_PICS.items():
        vp, rp = os.path.join(v2_res, dst), os.path.join(rotn, src)
        if os.path.exists(vp) and os.path.exists(rp) and Image.open(vp).size == Image.open(rp).size:
            os.makedirs(os.path.join(out_dir, os.path.dirname(dst)), exist_ok=True)
            Image.open(rp).save(os.path.join(out_dir, dst)); log.append('picture ' + dst)
    log += rotn_heroes.run(rotn, v2_res, out_dir)
    return log
