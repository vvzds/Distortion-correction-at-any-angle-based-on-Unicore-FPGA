from pathlib import Path
import os,json
W=Path(__file__).resolve().parent
inv=json.loads((W/'inventory.json').read_text(encoding='utf-8'))
print('ERROR SAMPLES',json.dumps(inv['errors'][:4],ensure_ascii=False))
roots=[Path(r['path']) for r in inv['roots'] if r['bytes']>150*1024**2]
rows=[]
for root in roots:
    for c in root.iterdir():
        size=0;count=0
        if c.is_file():size=c.stat().st_size;count=1
        elif c.is_dir():
            for b,ds,fs in os.walk(c,followlinks=False):
                ds[:]=[d for d in ds if not Path(b,d).is_symlink()]
                for f in fs:
                    try:size+=Path(b,f).stat().st_size;count+=1
                    except OSError:pass
        rows.append({'path':str(c),'bytes':size,'files':count})
(W/'detail.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
for r in sorted(rows,key=lambda x:-x['bytes'])[:45]:print(f"{r['bytes']/1024**3:.3f} GiB {r['files']:6} {r['path']}")
