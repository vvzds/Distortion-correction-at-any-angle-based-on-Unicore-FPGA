from pathlib import Path
import json,shutil,hashlib
BASE=Path('C:/Users/叶翔/Documents/Codex/fpga-main/deliverables/20261024/collab2_local_archive')
data={'pds_root_files':[(p.name,p.stat().st_size) for p in Path('D:/FPGA PDS').iterdir() if p.is_file()],'desktop_readme':Path('C:/Users/叶翔/Desktop/README.md').read_text(encoding='utf-8')[:1600]}
data['other_codex_files']={str(p):[x.name for x in p.iterdir()] for p in [Path('C:/Users/叶翔/Documents/Codex/2026-10-20/new-chat'),Path('C:/Users/叶翔/Documents/Codex/2026-10-14/new-chat')]}
print(json.dumps(data,ensure_ascii=False,indent=2))
for root in Path('C:/Users/叶翔/Documents/Codex').glob('20*/*'):
    if not root.is_dir() or root.name in {'x20','hatch-pet-c-users-codex-skills'}:continue
    names=[]
    for p in root.rglob('*'):
        if p.is_file():names.append(str(p.relative_to(root)))
        if len(names)>=8:break
    print(json.dumps({'root':str(root),'examples':names},ensure_ascii=False))
