"""Fix sprite atlases whose plist names a texture file that does not exist (V2 typos such as 'Sai_Skill..pvr.ccz').
Usage: python3 fix_plists.py <assets dir>"""
import os, sys, plistlib
root = sys.argv[1]
fixed = 0
for d, _, files in os.walk(root):
    for f in files:
        if not f.endswith('.plist'):
            continue
        p = os.path.join(d, f)
        try:
            data = plistlib.load(open(p, 'rb'))
        except Exception:
            continue
        m = data.get('metadata') if isinstance(data, dict) else None
        if not m or 'frames' not in data:
            continue
        names = [m.get('textureFileName'), m.get('realTextureFileName')]
        ok = [n for n in names if n and os.path.exists(os.path.join(d, n))]
        if m.get('textureFileName') and m['textureFileName'] not in ok:
            stem = f[:-6]
            cand = ok[0] if ok else next((x for x in sorted(os.listdir(d)) if x.startswith(stem + '.') and not x.endswith(('.plist', '.xml'))), None)
            if cand:
                print('fix', os.path.relpath(p, root), m['textureFileName'], '->', cand)
                m['textureFileName'] = cand
                m['realTextureFileName'] = cand
                plistlib.dump(data, open(p, 'wb'))
                fixed += 1
print('fixed', fixed)
