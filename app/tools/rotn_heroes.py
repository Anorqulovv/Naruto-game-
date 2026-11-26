"""Rise of the Ninja's extra heroes as heroes of their own in 2.2.

Rise of the Ninja put other characters into the V2 slots (its "Sakura" is Killer Bee, its "Pain" is Madara...).
Here every such character becomes a separate hero ("skin"): it fights with the slot hero's skills (same class,
same timings) but has RotN's sprites, pictures and voices. The slot hero itself keeps its V2 look.

Writes into the overlay:
  Unit/Ninja/<Slot>/<Skin>.plist/.png + <Skin>.xml   battle sprites + actions (V2 timings, RotN frames & sounds)
  Audio/<Skin>/*, Audio/Intro/<Skin>.ogg, Audio/Ougis/<Skin>_ougis.ogg
  <Skin>_* pictures (avatar, skill icons, labels, portraits, cut-in) are returned for the UI atlases.
"""
import os, re, shutil, filecmp
import xml.etree.ElementTree as ET
from atlas import load_frames, texture_path, premultiply, pvr_header_of, save_pvr_ccz, pack_items, write_plist
from PIL import Image

# skin id: (RotN slot / V2 class, name shown on the select screen)
SKINS = {
    'KillerBee': ('Sakura', 'Killer Bee'),
    'Madara': ('Pain', 'Uchiha Madara'),
    'Hashirama': ('Gaara', 'Senju Hashirama'),
    'Izuna': ('Choji', 'Uchiha Izuna'),
    'ZetsuSpiral': ('Hidan', 'Zetsu Spiral'),
    'KazekageGaara': ('Hinata', 'Kazekage Gaara'),
    'Obito': ('Jugo', 'Uchiha Obito'),
    'Sasori': ('Kankuro', 'Akasuna Sasori'),
    'Mei': ('Karin', 'Mei Terumi'),
    'JuubiObito': ('Kimimaro', 'Obito (Juubi)'),
    'Onoki': ('Konan', 'Tsuchikage Onoki'),
    'RikudoSennin': ('Neji', 'Rikudo Sennin'),
    'Zabuza': ('Orochimaru', 'Momochi Zabuza'),
    'Yagura': ('Sai', 'Isobu Yagura'),
    'Hanzo': ('Shikamaru', 'Hanzo'),
    'Temari': ('Shino', 'Temari'),
    'Shisui': ('Suigetsu', 'Uchiha Shisui'),
    'ObitoMask': ('Tenten', 'Obito (Mask)'),
    'Kaguya': ('Tobi', 'Otsutsuki Kaguya'),
    'NarutoKCM': ('Tsunade', 'Naruto KCM'),
    'RikudoMadara': ('Nagato', 'Rikudo Madara'),  # Madara's awakened form (not selectable)
}
# RotN slots whose sprites show another character than the slot hero (the slot hero keeps V2 art)
RESKINNED = {v[0] for v in SKINS.values()} | {'Ino', 'Kiba', 'Lee'}

# V2 heroes switch to "special" animations (skill10..12) in some modes: they replace idle / walk / normal
# attack. RotN has no frames for them, so a skin uses its own matching animation there.
SPECIAL = {
    'Hidan': {'skill10': 'idle', 'skill11': 'walk', 'skill12': 'nattack'},
    'Jugo': {'skill10': 'idle', 'skill11': 'walk', 'skill12': 'nattack'},
    'Suigetsu': {'skill10': 'idle', 'skill11': 'walk', 'skill12': 'nattack'},
    'Sai': {'skill10': 'nattack', 'skill11': 'idle', 'skill12': 'walk'},
    'Tobi': {'skill10': 'walk'},
}

UI_ATLASES = ['UI', 'Result', 'Report', 'Record', 'Record2', 'Select', 'Ougis', 'Ougis2']


class RotnPool:
    """RotN keeps part of a hero's action frames in Skills/<Slot>_Skill.plist (sometimes in another
    hero's atlas): find a frame by name in any RotN atlas, preferring the hero's own ones."""
    _cache = {}

    def __init__(self, rotn):
        import glob, plistlib
        self.rotn = rotn
        self.index = {}
        for p in sorted(glob.glob(os.path.join(rotn, 'Element', '**', '*.plist'), recursive=True) +
                        glob.glob(os.path.join(rotn, 'Skills', '*.plist'))):
            try:
                raw = open(p, 'rb').read()
                if not raw.lstrip().startswith(b'<?xml'):
                    raw = b'<?xml version="1.0" encoding="UTF-8"?>\n' + raw
                names = plistlib.loads(raw).get('frames', {})
            except Exception:
                continue
            for n in names:
                self.index.setdefault(n, []).append(p)

    def atlas(self, p):
        if p not in RotnPool._cache:
            t = texture_path(p)
            RotnPool._cache[p] = load_frames(p, t) if t else {}
        return RotnPool._cache[p]

    def get(self, name, slot):
        paths = self.index.get(name, [])
        if not paths:
            return None
        own = [q for q in paths if os.path.basename(q) in (slot + '.plist', slot + '_Skill.plist')]
        for q in own + [q for q in paths if q not in own]:
            fr = self.atlas(q)
            if name in fr:
                return fr[name]
        return None

    def frames(self, main, names, slot):
        """main frames + the named frames found elsewhere"""
        out = dict(main)
        for n in names:
            if n not in out:
                v = self.get(n, slot)
                if v is not None:
                    out[n] = v
        return out


_POOL = {}


def pool(rotn):
    if rotn not in _POOL:
        _POOL[rotn] = RotnPool(rotn)
    return _POOL[rotn]


def rotn_action_list(xml_path):
    """RotN xml -> {action: [('f', frame) | ('s', sound path)]} in file order."""
    txt = open(xml_path, encoding='utf-8', errors='replace').read()
    res = {}
    for m in re.finditer(r'<action\s+value="([^"]+)"(.*?)</action>', txt, re.S):
        seq = []
        for t in re.finditer(r'<frameName>\s*([^<\s]+)\s*</frameName>|<eventName\s+type="(setSound|setDSound)"\s*>\s*([^<]*?)\s*</eventName>', m.group(2)):
            if t.group(1):
                seq.append(('f', t.group(1)))
            else:
                seq.append(('s', t.group(3)))
        res[m.group(1).lower()] = seq
    return res


def is_voice(path):
    parts = path.split('/')
    return len(parts) >= 3 and parts[1] not in ('Effect', 'Menu', 'Ougis')


def copy_sound(rotn_root, path, skin, out_dir, copied, slot=None):
    """Audio/<Slot>/x.ogg from RotN -> Audio/<Skin>/x.ogg; shared sounds (Audio/Effect...) stay as they are."""
    src = os.path.join(rotn_root, path)
    parts = path.split('/')
    if not os.path.exists(src) and slot and len(parts) >= 3 and parts[1] not in ('Effect', 'Menu', 'Ougis'):
        # some RotN xmls name the folder differently (e.g. Audio/手鞠/ for Temari) than where the files are
        alt = 'Audio/%s/%s' % (slot, parts[-1])
        if os.path.exists(os.path.join(rotn_root, alt)):
            src, path, parts = os.path.join(rotn_root, alt), alt, alt.split('/')
    if len(parts) < 3 or parts[1] in ('Effect', 'Menu', 'Ougis') or not os.path.exists(src):
        return path if os.path.exists(src) or parts[1] in ('Effect', 'Menu') else None
    new = 'Audio/%s/%s' % (skin, parts[-1])
    if new not in copied:
        os.makedirs(os.path.join(out_dir, 'Audio', skin), exist_ok=True)
        shutil.copy(src, os.path.join(out_dir, new))
        copied.add(new)
    return new



# ---------------------------------------------------------------- RotN's own events for its heroes
# RotN draws most effects inside the hero's frames and spawns its own objects; V2's events of the slot hero
# spawn the slot hero's objects on top ("two skills at once"). A skin therefore uses RotN's events, keeping
# only what V2 can run, plus the V2 events the slot hero's class needs.
KNOWN_EFFECTS = {'n_hit', 'b_hit', 'l_hit', 'f_hit', 'f2_hit', 'c_hit', 'o_hit', 'o2_hit', 'ob_hit', 'ab_hit', 'ac_hit',
                 'ct_hit', 'ts_hit', 's_hit', 'bl_hit', 'bc_hit', 'bf_hit', 'sl_hit', 'a_hit', 'Kagura', 'Hupo', 'smk',
                 'tishen', 'stun', 'DarkFlame', 'Bagua', 'Kujiyose', 'kazi', 'sharingan', 'sharingan2', 'sharingan3',
                 'sharingan4', 'Hiraishin', 'Hiraishin2'}
GENERIC_CMDS = {'setInvincible', 'reInvincible', 'setTransport', 'reTransport', 'findTarget'}
SPAWNS = ('setMon', 'setBullet', 'setTrap', 'setClone')
ATTACK_ACTIONS = {'nattack', 'skill01', 'skill02', 'skill03', 'skill04', 'skill05', 'skill10', 'skill11', 'skill12'}


def rotn_events(xml_path):
    """RotN xml -> {action: [('f', frame) | ('e', type, value)]} in file order."""
    txt = open(xml_path, encoding='utf-8', errors='replace').read()
    res = {}
    for m in re.finditer(r'<action\s+value="([^"]+)"(.*?)</action>', txt, re.S):
        seq = []
        for t in re.finditer(r'<frameName>\s*([^<\s]+)\s*</frameName>|<eventName\s+type="(\w+)"\s*>\s*([^<]*?)\s*</eventName>', m.group(2)):
            seq.append(('f', t.group(1)) if t.group(1) else ('e', t.group(2), t.group(3)))
        res[m.group(1).lower()] = seq
    return res


_V2_FRAME_INDEX = {}


def v2_frame_index(v2_res):
    """frame name -> V2 atlas (relative path) holding it"""
    if v2_res not in _V2_FRAME_INDEX:
        import glob, plistlib
        idx = {}
        for p in glob.glob(os.path.join(v2_res, '**', '*.plist'), recursive=True):
            try:
                raw = open(p, 'rb').read()
                if not raw.lstrip().startswith(b'<?xml'):
                    raw = b'<?xml version="1.0" encoding="UTF-8"?>\n' + raw
                for n in plistlib.loads(raw).get('frames', {}):
                    idx.setdefault(n[:-4] if n.endswith('.png') else n, os.path.relpath(p, v2_res))
            except Exception:
                pass
        _V2_FRAME_INDEX[v2_res] = idx
    return _V2_FRAME_INDEX[v2_res]


def unit_atlas(v2_res, xml_rel):
    """the atlas that holds the first frame of a V2 unit xml (to preload it for a skin)"""
    try:
        first = re.search(r'<f>\s*([^<\s]+)\s*</f>', open(os.path.join(v2_res, xml_rel), encoding='utf-8', errors='replace').read())
    except OSError:
        return None
    return v2_frame_index(v2_res).get(first.group(1)) if first else None


def native_events(rotn, v2_res, skin, slot, aname, rseq, v2_kids, rframes, copied, out_dir, extra_atlases):
    """RotN's frames+events for one action translated to V2 xml elements (frames as ('f', rotn name)).
    None when RotN's events cannot do the job (then V2's events are spread over RotN's frames)."""
    v2_ev = [k for k in v2_kids if k.tag == 'e']
    v2_types = {k.get('type') for k in v2_ev}
    out, has_damage, rtypes, rcmds = [], False, set(), set()
    for it in rseq:
        if it[0] == 'f':
            if it[1] in rframes:
                out.append(('f', it[1]))
            continue
        _, t, v = it
        if t == 'setCommand':
            v = {'setInvicible': 'setInvincible', 'reInvicible': 'reInvincible'}.get(v, v)
            rcmds.add(v)
        if t in ('setSound', 'setDSound'):
            if is_voice(v):
                v = copy_sound(rotn, v, skin, out_dir, copied, slot)
            elif not os.path.exists(os.path.join(v2_res, v)):
                v = None
            if not v:
                continue
        elif t == 'setMon':
            if not os.path.exists(os.path.join(v2_res, 'Unit', 'Mon', v + '.xml')):
                continue
            extra_atlases.add(unit_atlas(v2_res, os.path.join('Unit', 'Mon', v + '.xml')))
        elif t in ('setBullet', 'setTrap'):
            if not os.path.exists(os.path.join(v2_res, 'Unit', 'Projectile', v + '.xml')):
                continue
            extra_atlases.add(unit_atlas(v2_res, os.path.join('Unit', 'Projectile', v + '.xml')))
        elif t == 'setSkillEffect':
            if v not in KNOWN_EFFECTS:
                continue
        elif t == 'setAttackBox':
            if v not in KNOWN_EFFECTS:
                v = 'c_hit'
        elif t == 'setClone':
            if 'setClone' not in v2_types:  # only where the slot hero's class makes clones
                continue
        elif t == 'setTransform':
            if 'setTransform' not in v2_types:  # the class decides which animation transforms the hero
                continue
        el = ET.Element('e', type=t)
        el.text = v
        out.append(('e', el))
        rtypes.add(t)
        if t == 'setAttackBox' or t in SPAWNS or t == 'setMonAttack':
            has_damage = True
    if not any(x[0] == 'f' for x in out):
        return None
    if aname in ATTACK_ACTIONS and not has_damage and any(k.get('type') in ('setAttackBox',) + SPAWNS for k in v2_ev):
        return None
    # V2 events the slot hero's class relies on
    nr = sum(1 for x in out if x[0] == 'f')
    nv = max(1, sum(1 for k in v2_kids if k.tag == 'f'))
    seen, keep = 0, []
    for k in v2_kids:
        if k.tag == 'f':
            seen += 1
            continue
        t, v = k.get('type'), (k.text or '').strip()
        need = (t == 'setTransform' and 'setTransform' not in rtypes) or \
               (t == 'setCommand' and v not in GENERIC_CMDS and v not in rcmds) or \
               (t == 'setBuff' and 'setBuff' not in rtypes) or \
               (t == 'setMonAttack' and 'setMonAttack' not in rtypes) or \
               (t == 'setActionResume' and 'setActionResume' not in rtypes)
        if need:
            keep.append((max(1, round(seen * nr / nv)) if seen else 0, k))
    if keep:
        res, fi = [], 0
        for x in out:
            while keep and keep[0][0] == fi and x[0] == 'f':
                res.append(('e', keep.pop(0)[1]))
            res.append(x)
            if x[0] == 'f':
                fi += 1
        res += [('e', k) for _, k in keep]
        out = res
    return out


def build_unit(rotn, v2_res, out_dir, skin, slot, log):
    v2_plist = os.path.join(v2_res, 'Unit', 'Ninja', slot, slot + '.plist')
    r_plist = os.path.join(rotn, 'Element', slot, slot + '.plist')
    v2_tex, r_tex = texture_path(v2_plist), texture_path(r_plist)
    if not r_tex:
        log.append('skin %s: no RotN texture for %s' % (skin, slot))
        return None
    racts = rotn_action_list(r_plist[:-6] + '.xml')
    revents = rotn_events(r_plist[:-6] + '.xml')
    extra_atlases = set()
    rframes = pool(rotn).frames(load_frames(r_plist, r_tex), [n for seq in racts.values() for t, n in seq if t == 'f'], slot)
    pvr = v2_tex.endswith('.pvr.ccz')
    tree = ET.parse(v2_plist[:-6] + '.xml')
    items, copied, sounds_used = {}, set(), []
    for action in tree.getroot().iter('action'):
        aname = (action.get('name') or '').lower()
        frame_el = action.find('frame')
        if frame_el is None:
            continue
        rseq = racts.get(aname, [])
        rlist = [n for t, n in rseq if t == 'f' and n in rframes]
        if not rlist and aname in SPECIAL.get(slot, {}):
            rseq = racts.get(SPECIAL[slot][aname], [])
            rlist = [n for t, n in rseq if t == 'f' and n in rframes]
        # only the hero's own voice lines are swapped; shared effect sounds stay
        rsounds = [copy_sound(rotn, n, skin, out_dir, copied, slot) for t, n in rseq if t == 's' and is_voice(n)]
        rsounds = [s for s in rsounds if s]
        kids = list(frame_el)
        nv = sum(1 for k in kids if k.tag == 'f')
        if nv == 0 or not rlist:
            continue
        rev = revents.get(aname) if rseq is racts.get(aname) else None
        native = native_events(rotn, v2_res, skin, slot, aname, rev, kids, rframes, copied, out_dir, extra_atlases) if rev else None
        if native:
            for k in kids:
                frame_el.remove(k)
            j = 0
            for x in native:
                if x[0] == 'f':
                    j += 1
                    fname = '%s_R_%s_%02d' % (skin, aname, j)
                    if fname not in items:
                        img, f = rframes[x[1]]
                        items[fname] = (premultiply(img) if pvr else img, f)
                    el = ET.Element('f')
                    el.text = fname
                    frame_el.append(el)
                else:
                    frame_el.append(x[1])
                    if x[1].get('type') in ('setSound', 'setDSound') and (x[1].text or '').startswith('Audio/%s/' % skin):
                        sounds_used.append(x[1].text)
            continue
        nr = len(rlist)
        events, seen = [], 0
        for k in kids:
            if k.tag == 'f':
                seen += 1
            else:
                events.append((seen, k))
        # V2 sound events get RotN's sounds of the same action (in order); extra V2 sounds are dropped
        si = 0
        for _, k in events:
            if k.get('type') in ('setSound', 'setDSound') and is_voice(k.text or ''):
                if si < len(rsounds):
                    k.text = rsounds[si]
                    sounds_used.append(rsounds[si])
                    si += 1
                else:
                    k.set('drop', '1')
        new, ei = [], 0
        for j in range(nr + 1):
            while ei < len(events) and (min(nr, round(events[ei][0] * nr / nv)) if events[ei][0] == 0 else max(1, min(nr, round(events[ei][0] * nr / nv)))) == j:
                if events[ei][1].get('drop') != '1':
                    new.append(events[ei][1])
                ei += 1
            if j < nr:
                fname = '%s_R_%s_%02d' % (skin, aname, j + 1)
                if fname not in items:
                    img, f = rframes[rlist[j]]
                    items[fname] = (premultiply(img) if pvr else img, f)
                el = ET.Element('f')
                el.text = fname
                new.append(el)
        for k in kids:
            frame_el.remove(k)
        for k in new:
            frame_el.append(k)
    # walking frames for the loading screen (<skin>_Walk_01..06)
    walk = [n for t, n in racts.get('walk', []) if t == 'f' and n in rframes] or [n for t, n in racts.get('idle', []) if t == 'f' and n in rframes]
    for i in range(6):
        if walk:
            img, f = rframes[walk[i * len(walk) // 6]]
            items['%s_Walk_%02d' % (skin, i + 1)] = (premultiply(img) if pvr else img, f)
    rel = os.path.join('Unit', 'Ninja', slot, skin)
    os.makedirs(os.path.join(out_dir, os.path.dirname(rel)), exist_ok=True)
    tex, fr = pack_items(items)
    if pvr:
        save_pvr_ccz(tex, os.path.join(out_dir, rel + '.pvr.ccz'), pvr_header_of(v2_tex))
        write_plist(os.path.join(out_dir, rel + '.plist'), fr, skin + '.pvr.ccz', tex.size)
    else:
        tex.save(os.path.join(out_dir, rel + '.png'), optimize=True)
        write_plist(os.path.join(out_dir, rel + '.plist'), fr, skin + '.png', tex.size)
    tree.write(os.path.join(out_dir, rel + '.xml'), encoding='utf-8', xml_declaration=True)
    # atlases of the objects RotN's events spawn (loaded with the skin)
    extra_atlases.discard(None)
    with open(os.path.join(out_dir, rel + '_extra.txt'), 'w') as fh:
        fh.write('\n'.join(sorted(extra_atlases)) + '\n')
    log.append('skin %s (%s): %d frames, %d sounds' % (skin, slot, len(items), len(copied)))
    return sounds_used


def voices(rotn, v2_res, out_dir, skin, slot, sounds_used):
    """Intro voice (select screen) and ougi voice (cut-in) for a skin."""
    adir = os.path.join(rotn, 'Audio', slot)
    files = sorted(os.listdir(adir)) if os.path.isdir(adir) else []
    intro = next((f for f in files if 'intro' in f.lower()), None)
    pick = os.path.join(adir, intro) if intro else None
    if not pick:
        own = [s for s in sounds_used if s.startswith('Audio/%s/' % skin)]
        if own:
            pick = os.path.join(out_dir, own[-1])
    for sub, name in (('Intro', skin + '.ogg'), ('Ougis', skin + '_ougis.ogg')):
        dst = os.path.join(out_dir, 'Audio', sub, name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        src = pick
        if sub == 'Ougis':
            r_ougi = os.path.join(rotn, 'Audio', 'Ougis', slot + '_ougis.ogg')
            v_ougi = os.path.join(v2_res, 'Audio', 'Ougis', slot + '_ougis.ogg')
            if os.path.exists(r_ougi) and (not os.path.exists(v_ougi) or not filecmp.cmp(r_ougi, v_ougi, shallow=False)):
                src = r_ougi
        if src and os.path.exists(src):
            shutil.copy(src, dst)


def name_tag(text):
    """Kill report name picture (<hero>_rpf.png): white letters with a warm glow, like V2's."""
    from PIL import ImageDraw, ImageFont, ImageFilter
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 17)
    w = int(font.getlength(text)) + 8
    img = Image.new('RGBA', (w, 23))
    glow = Image.new('RGBA', img.size)
    ImageDraw.Draw(glow).text((4, 1), text, font=font, fill=(150, 110, 60, 255))
    glow = glow.filter(ImageFilter.GaussianBlur(2))
    img.alpha_composite(glow)
    img.alpha_composite(glow)
    ImageDraw.Draw(img).text((4, 1), text, font=font, fill=(255, 255, 255, 255))
    return img


def ui_frames(rotn, v2_res):
    """{atlas: {<Skin>_x.png: (img, frame)}} copied from RotN's <Slot>_x.png pictures."""
    out = {}
    for a in UI_ATLASES:
        rp = os.path.join(rotn, a + '.plist')
        if not os.path.exists(rp) or not texture_path(rp):
            continue
        r = load_frames(rp, texture_path(rp))
        add = {}
        for skin, (slot, _) in SKINS.items():
            for k, (img, f) in r.items():
                if k.startswith(slot + '_') and img.getbbox():
                    add[skin + k[len(slot):]] = (img, f)
        if a == 'Report':
            # the kill report shows the hero's name: RotN only has the slot hero's one
            for skin, (slot, title) in SKINS.items():
                img = name_tag(title)
                add[skin + '_rpf.png'] = (img, {'offset': '{0,0}', 'sourceColorRect': '{{0,0},{%d,%d}}' % img.size,
                                                'sourceSize': '{%d,%d}' % img.size})
        out[a] = add
    return out


# V2 effect groups of the slot hero -> RotN effect group of the skin (RotN names its effects differently)
EFFECT_MAP = {
    'Hashirama': {'sabaku_move': 'mokuton_02', 'sandball_move': 'mokuton_01', 'sandhand_move': 'mokuton_01',
                  'sandwave_move': 'mokuton_01'},
}


def skin_effects(rotn, v2_res, out_dir, skin, slot, log):
    """<Skin>_Skill atlas: the slot hero's V2 effect frames (same names, so the V2 code finds them) with
    RotN's effects of that slot where the frame groups match. Loaded before the slot's own atlas."""
    from rotn_skin import groups
    v2p = os.path.join(v2_res, 'Unit', 'Ninja', slot, slot + '_Skill.plist')
    rp = os.path.join(rotn, 'Element', 'Skills', slot + '_Skill.plist')
    if not os.path.exists(v2p) or not os.path.exists(rp) or not texture_path(rp) or not texture_path(v2p):
        return
    items = load_frames(v2p, texture_path(v2p))
    rframes = load_frames(rp, texture_path(rp))
    pvr = texture_path(v2p).endswith('.pvr.ccz')
    gv, gr = groups(items), groups(rframes)
    n = 0
    emap = EFFECT_MAP.get(skin, {})
    for g, names in gv.items():
        src = gr.get(emap.get(g, g))
        if not src or (g not in emap and len(src) != len(names)):
            continue
        for i, a in enumerate(names):  # resample when the frame counts differ
            img, f = rframes[src[min(len(src) - 1, i * len(src) // len(names))]]
            items[a] = (premultiply(img) if pvr else img, f)
            n += 1
    if not n:
        return
    rel = os.path.join('Unit', 'Ninja', slot, skin + '_Skill')
    tex, fr = pack_items(items)
    if pvr:
        save_pvr_ccz(tex, os.path.join(out_dir, rel + '.pvr.ccz'), pvr_header_of(texture_path(v2p)))
        write_plist(os.path.join(out_dir, rel + '.plist'), fr, skin + '_Skill.pvr.ccz', tex.size)
    else:
        tex.save(os.path.join(out_dir, rel + '.png'), optimize=True)
        write_plist(os.path.join(out_dir, rel + '.plist'), fr, skin + '_Skill.png', tex.size)
    log.append('skin %s effects: %d RotN frames' % (skin, n))


def run(rotn, v2_res, out_dir):
    log = []
    for skin, (slot, _) in SKINS.items():
        try:
            used = build_unit(rotn, v2_res, out_dir, skin, slot, log)
            if used is not None:
                voices(rotn, v2_res, out_dir, skin, slot, used)
            skin_effects(rotn, v2_res, out_dir, skin, slot, log)
        except Exception as e:
            log.append('ERROR skin %s: %s' % (skin, e))
    return log
