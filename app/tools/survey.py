import sys, os, re, glob
sys.path.insert(0, os.path.dirname(__file__)); from atlas import *
from PIL import ImageChops
R='v2/projects/NarutoSenki/Resources/Unit'
def act_frames(fr):
    acts={}
    for n in fr:
        m=re.match(r'(.+)_(\d+)(\.png)?$', n)
        if m: acts.setdefault(m.group(1).lower(),[]).append((int(m.group(2)),n))
    return {k:[n for _,n in sorted(v)] for k,v in acts.items()}
tot=dict(same=0,diffart=0,diffcount=0,rotn_only=0)
for rp in sorted(glob.glob('assets/Element/*/*.plist')):
    name=os.path.basename(rp)[:-6]
    v=glob.glob(f'{R}/*/{name}/{name}.plist') or glob.glob(f'{R}/*/*/{name}.plist') or glob.glob(f'{R}/*/{name}.plist')
    if not v: print('NO V2', rp); continue
    if not os.path.exists(texture_path(rp)): print('NO ROTN TEX', rp); continue
    try: a=load_frames(rp); b=load_frames(v[0])
    except Exception as e: print('ERR',rp,e); continue
    A,B=act_frames(a),act_frames(b); s=dict(same=0,diffart=0,diffcount=0)
    for k in B:
        if k not in A: continue
        if len(A[k])!=len(B[k]): s['diffcount']+=1; continue
        d=any(a[x][0].size!=b[y][0].size or ImageChops.difference(a[x][0],b[y][0]).getbbox() for x,y in zip(A[k],B[k]))
        s['diffart' if d else 'same']+=1
    print(name, v[0].split('Unit/')[1], s, 'v2acts',len(B),'rotnacts',len(A))
