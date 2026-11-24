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
}
# RotN slots whose sprites show another character than the slot hero (the slot hero keeps V2 art)
RESKINNED = {v[0] for v in SKINS.values()} | {'Ino', 'Kiba', 'Lee'}

UI_ATLASES = ['UI', 'Result', 'Report', 'Record', 'Record2', 'Select', 'Ougis', 'Ougis2']


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


def copy_sound(rotn_root, path, skin, out_dir, copied):
    """Audio/<Slot>/x.ogg from RotN -> Audio/<Skin>/x.ogg; shared sounds (Audio/Effect...) stay as they are."""
    src = os.path.join(rotn_root, path)
    parts = path.split('/')
    if len(parts) < 3 or parts[1] in ('Effect', 'Menu', 'Ougis') or not os.path.exists(src):
        return path if os.path.exists(src) or parts[1] in ('Effect', 'Menu') else None
    new = 'Audio/%s/%s' % (skin, parts[-1])
    if new not in copied:
        os.makedirs(os.path.join(out_dir, 'Audio', skin), exist_ok=True)
        shutil.copy(src, os.path.join(out_dir, new))
        copied.add(new)
    return new


def build_unit(rotn, v2_res, out_dir, skin, slot, log):
    v2_plist = os.path.join(v2_res, 'Unit', 'Ninja', slot, slot + '.plist')
    r_plist = os.path.join(rotn, 'Element', slot, slot + '.plist')
    v2_tex, r_tex = texture_path(v2_plist), texture_path(r_plist)
    if not r_tex:
        log.append('skin %s: no RotN texture for %s' % (skin, slot))
        return None
    rframes = load_frames(r_plist, r_tex)
    racts = rotn_action_list(r_plist[:-6] + '.xml')
    pvr = v2_tex.endswith('.pvr.ccz')
    tree = ET.parse(v2_plist[:-6] + '.xml')
    items, copied, sounds_used = {}, set(), []
    for action in tree.getroot().iter('action'):
        aname = (action.get('name') or '').lower()
        frame_el = action.find('frame')
        if frame_el is None or aname not in racts:
            continue
        rseq = racts[aname]
        rlist = [n for t, n in rseq if t == 'f' and n in rframes]
        # only the hero's own voice lines are swapped; shared effect sounds stay
        rsounds = [copy_sound(rotn, n, skin, out_dir, copied) for t, n in rseq if t == 's' and is_voice(n)]
        rsounds = [s for s in rsounds if s]
        kids = list(frame_el)
        nv = sum(1 for k in kids if k.tag == 'f')
        if nv == 0 or not rlist:
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
        out[a] = add
    return out


def run(rotn, v2_res, out_dir):
    log = []
    for skin, (slot, _) in SKINS.items():
        try:
            used = build_unit(rotn, v2_res, out_dir, skin, slot, log)
            if used is not None:
                voices(rotn, v2_res, out_dir, skin, slot, used)
        except Exception as e:
            log.append('ERROR skin %s: %s' % (skin, e))
    return log
