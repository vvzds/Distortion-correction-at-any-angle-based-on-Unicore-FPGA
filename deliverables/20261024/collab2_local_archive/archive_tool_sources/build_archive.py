"""Lossless content-addressed project archive, with original Git object reuse."""
from pathlib import Path
import json,hashlib,zipfile,zlib,os,struct,time,collections,sys,shutil
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from hash_inventory import native
REPO=Path('C:/Users/叶翔/Documents/Codex/fpga-main')
DEST=REPO/'deliverables/20261024/collab2_local_archive'
LIMIT=44*1024**2
CHUNK=8*1024**2

def digest(data):return hashlib.sha256(data).hexdigest()

class Builder:
    def __init__(self):
        self.data=json.loads((HERE/'local_objects.json').read_text(encoding='utf-8'))
        self.objects=self.data['objects'];self.remote=json.loads((HERE/'remote_git_objects.json').read_text(encoding='utf-8'))
        self.storage={};self.chunks={};self.packs=[];self.writer=None;self.active=set()
        DEST.mkdir(exist_ok=True);(DEST/'packs').mkdir(exist_ok=True)

    def remote_refs(self):
        for sha,obj in self.objects.items():
            if obj['git_blob'] in self.remote['objects']:
                ref=self.remote['objects'][obj['git_blob']][0]
                self.storage[sha]={'kind':'git','oid':obj['git_blob'],'commit':ref['commit'],'path':ref['path']}
        for item in json.loads((HERE/'remote_manifests/index.json').read_text(encoding='utf-8')):
            if not item['path'].endswith('parts_manifest.json'):continue
            meta=json.loads((HERE/'remote_manifests'/item['file']).read_text(encoding='utf-8'))
            sha=meta['sha256']
            if sha not in self.objects:continue
            obj=self.objects[sha];parts=[]
            with open(native(obj['paths'][0]['path']),'rb') as f:
                for part in meta['parts']:
                    raw=f.read(part['bytes'])
                    assert digest(raw)==part['sha256']
                    oid=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
                    path=str(Path(item['path']).parent/part['path']).replace('\\','/')
                    assert any(r['commit']==item['commit'] and r['path']==path for r in self.remote['objects'][oid])
                    parts.append({'oid':oid,'commit':item['commit'],'path':path,'size':len(raw)})
                assert not f.read(1)
            self.storage[sha]={'kind':'git_concat','parts':parts}
        print('EXISTING OBJECTS '+str(len(self.storage)),flush=True)

    def write_chunk(self,raw):
        sha=digest(raw)
        if sha in self.chunks:return sha
        compressed=zlib.compress(raw,6)
        if self.writer is None or self.writer.fp.tell()+len(compressed)+256>LIMIT:
            if self.writer:self.close_pack()
            name='packs/part%04d.zip'%(len(self.packs)+1)
            self.writer=zipfile.ZipFile(DEST/name,'w',compression=zipfile.ZIP_STORED,allowZip64=True)
            self.pack_name=name
        self.writer.writestr(sha,compressed)
        self.chunks[sha]={'pack':self.pack_name,'size':len(raw),'compressed_size':len(compressed)}
        return sha

    def close_pack(self):
        self.writer.close();p=DEST/self.pack_name
        self.packs.append({'path':self.pack_name,'bytes':p.stat().st_size,'sha256':digest(p.read_bytes())})
        print('PACK '+self.pack_name+' '+str(p.stat().st_size),flush=True)
        self.writer=None

    def region(self,f,offset,length,allow_object=False):
        f.seek(offset)
        if allow_object and length>1024**2:
            h=hashlib.sha256()
            remaining=length
            while remaining:
                raw=f.read(min(CHUNK,remaining));assert raw;remaining-=len(raw);h.update(raw)
            sha=h.hexdigest()
            if sha in self.objects and sha not in self.active:
                self.encode(sha)
                return [{'object':sha}]
            f.seek(offset)
        parts=[]
        while length:
            raw=f.read(min(length,CHUNK));assert raw
            parts.append({'chunk':self.write_chunk(raw)})
            length-=len(raw)
        return parts

    def encode(self,sha):
        if sha in self.storage:return
        obj=self.objects[sha];p=obj['paths'][0]['path'];self.active.add(sha)
        parts=[]
        with open(native(p),'rb') as f:
            # Split ZIPs at original byte boundaries. Stored nested files can reuse
            # an existing object without recompressing or changing any original ZIP byte.
            try:
                iszip=obj['size']>16*1024**2 and zipfile.is_zipfile(f)
            except OSError:iszip=False
            if iszip:
                f.seek(0)
                with zipfile.ZipFile(f) as z:
                    entries=sorted(z.infolist(),key=lambda i:i.header_offset)
                    ranges=[]
                    for info in entries:
                        f.seek(info.header_offset);header=f.read(30)
                        if len(header)!=30 or header[:4]!=b'PK\x03\x04':raise ValueError('bad ZIP header')
                        name_len,extra_len=struct.unpack_from('<HH',header,26)
                        start=info.header_offset+30+name_len+extra_len
                        ranges.append((start,info.compress_size,info.compress_type))
                    cursor=0
                    for start,size,compression in ranges:
                        if start<cursor:raise ValueError('overlapping ZIP entries')
                        parts+=self.region(f,cursor,start-cursor)
                        parts+=self.region(f,start,size,compression==zipfile.ZIP_STORED)
                        cursor=start+size
                    parts+=self.region(f,cursor,obj['size']-cursor)
            else:parts=self.region(f,0,obj['size'])
        self.storage[sha]={'kind':'recipe','parts':parts}
        self.active.remove(sha)

    def run(self):
        self.remote_refs()
        for n,sha in enumerate(self.objects,1):
            self.encode(sha)
            if n%1000==0:print('ENCODED '+str(n)+'/'+str(len(self.objects)),flush=True)
        if self.writer:self.close_pack()
        manifest={'format':'collab2-lossless-archive-v1','created':time.strftime('%Y-%m-%dT%H:%M:%S'),'source_commits':self.remote['commits'],'objects':{},'chunks':self.chunks,'packs':self.packs,'scan_errors':self.data['errors']}
        paths=[]
        for sha,obj in self.objects.items():
            manifest['objects'][sha]={'size':obj['size'],'git_blob':obj['git_blob'],'storage':self.storage[sha]}
            for alias in obj['paths']:paths.append({**alias,'sha256':sha,'size':obj['size']})
        (DEST/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        with (DEST/'PATHS.jsonl').open('w',encoding='utf-8') as f:
            for row in paths:f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
        for filename in ['filtered_exclusions.json','00_归档开工声明_给管理方及一号.md']:
            shutil.copy2(HERE/filename,DEST/filename)
        summary={'files':len(paths),'unique_files':len(self.objects),'original_bytes':self.data['original_total_bytes'],'unique_bytes':self.data['unique_bytes'],'reused_remote_objects':sum(s['kind'].startswith('git') for s in self.storage.values()),'packs':len(self.packs),'new_payload_bytes':sum(p['bytes'] for p in self.packs),'scan_errors':self.data['errors']}
        (DEST/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':Builder().run()
