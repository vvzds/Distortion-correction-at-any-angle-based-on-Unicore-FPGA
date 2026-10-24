"""Restore one selected historical project tree with byte-exact SHA256 checks.

Python standard library only. Run --list first. Git resolves existing repository
objects; new payloads are losslessly reconstructed from bounded ZIP pack files.
"""
from pathlib import Path,PurePosixPath
import argparse,json,hashlib,subprocess,shutil,os,zipfile,zlib,tempfile,gzip

def native(path):
    p=os.path.abspath(path)
    return '\\\\?\\'+p if os.name=='nt' and not p.startswith('\\\\?\\') else p

class Reader:
    def __init__(self,archive,repo=None,git=None,remote_reader=None):
        self.base=Path(archive).resolve()
        self.manifest=json.loads((self.base/'MANIFEST.json').read_text(encoding='utf-8'))
        self.repo=Path(repo).resolve() if repo else self.base.parents[2]
        self.git=git or shutil.which('git')
        self.remote_reader=remote_reader
        self.packs={};self.checked=set();self.cache=None

    def close(self):
        for z in self.packs.values():z.close()
        if self.cache:self.cache.cleanup()

    def chunk(self,sha):
        entry=self.manifest['chunks'][sha]
        name=entry['pack']
        if name not in self.packs:
            if name not in self.checked:
                info=next(p for p in self.manifest['packs'] if p['path']==name)
                h=hashlib.sha256()
                with open(native(self.base/name),'rb') as f:
                    for block in iter(lambda:f.read(1024**2),b''):h.update(block)
                if h.hexdigest()!=info['sha256']:raise ValueError('Pack SHA256 mismatch: '+name)
                self.checked.add(name)
            self.packs[name]=zipfile.ZipFile(native(self.base/name))
        data=zlib.decompress(self.packs[name].read(sha))
        if len(data)!=entry['size'] or hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Chunk SHA256 mismatch: '+sha)
        return data

    def remote(self,oid):
        if self.remote_reader:
            yield from self.remote_reader(oid);return
        if not self.git:raise RuntimeError('Git is required for existing repository objects; use --git')
        if self.cache is None:self.cache=tempfile.TemporaryDirectory(prefix='.fpga_restore_',dir=str(Path.cwd()),ignore_cleanup_errors=True)
        cached=Path(self.cache.name)/oid
        if not cached.exists():
            with cached.open('wb') as out:
                result=subprocess.run([self.git,'-C',str(self.repo),'-c','http.sslBackend=openssl','cat-file','blob',oid],stdout=out,stderr=subprocess.PIPE)
            if result.returncode:raise RuntimeError('Cannot read Git object '+oid+': '+result.stderr.decode('utf-8','replace'))
            h=hashlib.sha1(b'blob '+str(cached.stat().st_size).encode()+b'\0')
            with cached.open('rb') as f:
                for data in iter(lambda:f.read(1024**2),b''):h.update(data)
            if h.hexdigest()!=oid:raise ValueError('Git object mismatch')
        with cached.open('rb') as f:
            yield from iter(lambda:f.read(1024**2),b'')

    def stream(self,sha,active=()):
        if sha in active:raise ValueError('Archive object cycle')
        obj=self.manifest['objects'][sha];storage=obj['storage'];kind=storage['kind']
        if kind=='git':yield from self.remote(storage['oid'])
        elif kind=='git_concat':
            for part in storage['parts']:yield from self.remote(part['oid'])
        elif kind=='recipe':
            for part in storage['parts']:
                if 'chunk' in part:yield self.chunk(part['chunk'])
                else:yield from self.stream(part['object'],active+(sha,))
        else:raise ValueError('Unsupported storage kind: '+kind)

    def restore(self,sha,path,overwrite=False):
        path=Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists() and not overwrite:
            h=hashlib.sha256()
            with open(native(path),'rb') as f:
                for data in iter(lambda:f.read(1024**2),b''):h.update(data)
            if h.hexdigest()==sha:return 'already_verified'
            raise FileExistsError(str(path)+' differs; use another destination or --overwrite')
        temporary=str(path)+'.restore-partial'
        h=hashlib.sha256();size=0
        try:
            with open(native(temporary),'wb') as f:
                for data in self.stream(sha):f.write(data);h.update(data);size+=len(data)
            if h.hexdigest()!=sha or size!=self.manifest['objects'][sha]['size']:raise ValueError('Restored object SHA256/size mismatch: '+sha)
            os.replace(native(temporary),native(path))
        finally:
            if os.path.exists(native(temporary)):os.remove(native(temporary))
        return 'restored'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--repo',type=Path)
    parser.add_argument('--git')
    parser.add_argument('--list',action='store_true')
    parser.add_argument('--root')
    parser.add_argument('--prefix',default='')
    parser.add_argument('--destination',type=Path)
    parser.add_argument('--overwrite',action='store_true')
    args=parser.parse_args();base=args.archive.resolve()
    rows=[]
    pathfile=base/'PATHS.jsonl'
    handle=pathfile.open(encoding='utf-8') if pathfile.exists() else gzip.open(base/'PATHS.jsonl.gz','rt',encoding='utf-8')
    with handle as f:
        for line in f:
            r=json.loads(line)
            if args.root and r['root']!=args.root:continue
            if args.prefix and not r['rel'].startswith(args.prefix.rstrip('/')+'/') and r['rel']!=args.prefix.rstrip('/'):continue
            rows.append(r)
    if args.list:
        groups={}
        for r in rows:
            key=r['root']+'/'+r['rel'].split('/')[0]
            groups[key]=groups.get(key,0)+1
        print(json.dumps(groups,ensure_ascii=False,indent=2));return
    if not args.root or not args.destination:parser.error('Restoration requires --root and --destination; use --list first')
    reader=Reader(base,args.repo,args.git)
    try:
        for r in rows:
            rel=PurePosixPath(r['rel'])
            if rel.is_absolute() or '..' in rel.parts or any(':' in p for p in rel.parts):raise ValueError('Unsafe archive relative path')
            target=args.destination.joinpath(*rel.parts)
            reader.restore(r['sha256'],target,args.overwrite)
        print('RESTORE PASS: '+str(len(rows))+' files, SHA256 verified')
    finally:reader.close()

if __name__=='__main__':main()
