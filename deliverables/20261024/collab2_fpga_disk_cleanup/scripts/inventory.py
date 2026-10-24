from pathlib import Path
import os,json,time
W=Path(__file__).resolve().parent
roots=[Path('D:/FPGA PDS'),Path('C:/Users/叶翔/Desktop/yx'),W.parent]
rows=[];errors=[]
for root in roots:
    for child in root.iterdir():
        if not child.is_dir() or child.name in ('site','fpga_cleanup_20261024'):continue
        size=0;count=0;largest=[]
        for base,dirs,files in os.walk(child,followlinks=False,onerror=lambda e:errors.append(str(e))):
            dirs[:]=[d for d in dirs if not Path(base,d).is_symlink() and d!='.git']
            for name in files:
                p=Path(base,name)
                try:
                    s=p.stat();size+=s.st_size;count+=1
                    if s.st_size>=100*1024*1024:largest.append({'path':str(p),'bytes':s.st_size})
                except OSError as e:errors.append(str(e))
        rows.append({'path':str(child),'bytes':size,'files':count,'large_files':largest})
(W/'inventory.json').write_text(json.dumps({'roots':rows,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
for r in sorted(rows,key=lambda x:-x['bytes'])[:35]:print(f"{r['bytes']/1024**3:.3f} GiB  {r['files']:7}  {r['path']}")
print('Errors:',len(errors))
