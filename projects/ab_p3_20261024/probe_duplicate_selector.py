"""Exhaustive two-state check of a prospective cache-only duplicate selector.
No production or P3 RTL is modified. Tests all qfound patterns, including
unreachable mixtures, rather than assuming earlier keys are already found.
"""
from pathlib import Path
import itertools,json,hashlib
R=Path(__file__).resolve().parent
count=0
for same_row,same_seg,found_mask,which in itertools.product(range(2),range(2),range(16),range(4)):
    rows=[20,20 if same_row else 21]
    segs=[5,5 if same_seg else 6]
    found=[bool(found_mask&(1<<k)) for k in range(4)]
    original=which
    original_found=found[which]
    for k in range(4):
        if k<which and found[k] and rows[k//2]==rows[which//2] and segs[k%2]==segs[which%2]:
            original=k;original_found=True
    selected=which
    if which==1:
        if found[0] and same_seg:selected=0
    elif which==2:
        if found[1] and same_row and same_seg:selected=1
        elif found[0] and same_row:selected=0
    elif which==3:
        if found[2] and same_seg:selected=2
        elif found[1] and same_row:selected=1
        elif found[0] and same_row and same_seg:selected=0
    assert (selected,found[selected])==(original,original_found), (same_row,same_seg,found_mask,which)
    count+=1
out={'cases':count,'passed':True,'domain':'All 2-state row/segment equality flags, qfound masks and qwhich; selector identity implies equality for all qid data values',
     'scope':'Prospective local factorization only; not RTL sequential equivalence, not timing evidence',
     'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(R/'results/duplicate_selector_probe.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
