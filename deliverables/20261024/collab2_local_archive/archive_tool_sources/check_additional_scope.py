from pathlib import Path
import json,os
root=Path('C:/Users/叶翔/Documents/Codex/a1024m01/M01')
files=[p for p in root.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts]
print(json.dumps({'root':str(root),'files':len(files),'bytes':sum(p.stat().st_size for p in files),'examples':[str(p.relative_to(root)) for p in files[:35]]},ensure_ascii=False,indent=2))
