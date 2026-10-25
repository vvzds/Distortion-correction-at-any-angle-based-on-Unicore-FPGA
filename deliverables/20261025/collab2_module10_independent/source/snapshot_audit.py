"""Audit real candidate readback bytes; no serial command or register write."""
import argparse,json,hashlib
from pathlib import Path
REGS=[0x3503,0x3406,0x3500,0x3501,0x3502,0x350a,0x350b,0x350c,0x350d,
      0x3400,0x3401,0x3402,0x3403,0x3404,0x3405]
def decode(value):
    if len(value)!=15:raise ValueError('Snapshot requires exactly 15 bytes')
    r=dict(zip(REGS,value))
    if r[0x3503]&3!=3 or r[0x3406]&1!=1:raise ValueError('AEC/AGC/AWB not all manual')
    return dict(registers={f'{a:04X}':f'{v:02X}' for a,v in r.items()},
        exposure_line_sixteenths=((r[0x3500]&15)<<16)|(r[0x3501]<<8)|r[0x3502],
        gain_raw=((r[0x350a]&3)<<8)|r[0x350b],extra_vts_lines=(r[0x350c]<<8)|r[0x350d],
        awb_gain_raw={c:((r[a]&15)<<8)|r[a+1] for c,a in [('R',0x3400),('G',0x3402),('B',0x3404)]},
        exposure_ms=None,exposure_ms_note='Requires verified runtime line period; do not infer from lens datasheet')
def audit(document):
    if document.get('evidence_kind')!='REAL_BOARD_READBACK':raise ValueError('Need real readback provenance')
    for key in ('bitstream_sha256','snapshot_transport_evidence_sha256'):
        v=document.get(key,'')
        if len(v)!=64 or any(c not in '0123456789abcdef' for c in v):raise ValueError('Missing SHA256 '+key)
    before=bytes.fromhex(document['before_snapshot_hex']);after=bytes.fromhex(document['after_snapshot_hex'])
    decoded=decode(before);decode(after)
    if before!=after:raise ValueError('Exposure/gain/WB changed during comparison')
    if document.get('snapshot_valid_before') is not True or document.get('snapshot_valid_after') is not True:
        raise ValueError('Snapshot valid flag required at both ends')
    return dict(status='REGISTER_STABILITY_VERIFIED',decoded=decoded,
        bitstream_sha256=document['bitstream_sha256'],quality_acceptance='NOT_EVALUATED',
        limitation='Hashes bind caller-supplied evidence; they do not independently attest physical hardware or lighting')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('readback',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():raise ValueError('Output exists')
    r=audit(json.loads(a.readback.read_text(encoding='utf-8')))
    r['readback_file_sha256']=hashlib.sha256(a.readback.read_bytes()).hexdigest()
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
