"""Decode every archived object and check exact hashes against the local snapshot."""
from pathlib import Path
import sys,json,hashlib,zipfile,time,collections
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from restore_archive import Reader
from hash_inventory import native
BASE=Path('C:/Users/叶翔/Documents/Codex/fpga-main/deliverables/20261024/collab2_local_archive')

def main():
    local=json.loads((HERE/'local_objects.json').read_text(encoding='utf-8'))['objects']
    reader=Reader(BASE);sources={}
    for sha,obj in reader.manifest['objects'].items():
        storage=obj['storage'];path=local[sha]['paths'][0]['path']
        if storage['kind']=='git':sources[storage['oid']]=(path,0,obj['size'])
        elif storage['kind']=='git_concat':
            offset=0
            for part in storage['parts']:
                sources[part['oid']]=(path,offset,part['size']);offset+=part['size']
    checked=set()
    def remote(oid):
        path,offset,length=sources[oid]
        h=hashlib.sha1(b'blob '+str(length).encode()+b'\0');remaining=length
        with open(native(path),'rb') as f:
            f.seek(offset)
            while remaining:
                data=f.read(min(2**20,remaining))
                if not data:raise ValueError('Unexpected EOF')
                remaining-=len(data);h.update(data);yield data
        if h.hexdigest()!=oid:raise ValueError('Remote Git reference differs from local bytes')
        checked.add(oid)
    reader.remote_reader=remote
    failed=[]
    for n,(sha,obj) in enumerate(reader.manifest['objects'].items(),1):
        h=hashlib.sha256();size=0
        try:
            for data in reader.stream(sha):h.update(data);size+=len(data)
            if h.hexdigest()!=sha or size!=obj['size']:raise ValueError('Object hash/size mismatch')
        except Exception as e:failed.append({'sha256':sha,'error':str(e)})
        if n%1000==0:print('VERIFIED '+str(n)+'/'+str(len(local)),flush=True)
    # Ensure even a chunk used only in an empty or unusual recipe is checked.
    for sha in reader.manifest['chunks']:reader.chunk(sha)
    result={'state':'PASS' if not failed else 'FAIL','objects_checked':len(local),'file_aliases':sum(len(x['paths']) for x in local.values()),'remote_git_objects_content_verified':len(checked),'pack_hashes_checked':len(reader.checked),'chunks_checked':len(reader.manifest['chunks']),'errors':failed,'method':'All object recipes decoded; every resulting SHA256 and size checked. Reused Git references checked by exact Git blob SHA1 against local bytes; no large remote redownload needed.'}
    reader.close()
    (BASE/'VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    if failed:raise SystemExit(1)

if __name__=='__main__':main()
