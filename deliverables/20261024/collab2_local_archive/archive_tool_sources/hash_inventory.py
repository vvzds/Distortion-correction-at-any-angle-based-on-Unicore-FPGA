from pathlib import Path
import os,json,hashlib,collections,concurrent.futures,time,zipfile,sys

HERE=Path(__file__).resolve().parent
def native(path):
    p=os.path.abspath(path)
    return '\\\\?\\'+p if os.name=='nt' and not p.startswith('\\\\?\\') else p

def hashes(row):
    p=native(row['path'])
    a=hashlib.sha256();b=hashlib.sha1(b'blob '+str(row['size']).encode()+b'\0')
    try:
        with open(p,'rb') as f:
            for data in iter(lambda:f.read(2**20),b''):a.update(data);b.update(data)
        st=os.stat(p)
        if st.st_size!=row['size'] or st.st_mtime_ns!=row['mtime_ns']:raise RuntimeError('file changed during inventory')
        return {**row,'sha256':a.hexdigest(),'git_blob':b.hexdigest()}
    except Exception as e:return {**row,'error':str(e)}

def main():
    d=json.loads((HERE/'inventory.json').read_text(encoding='utf-8'))
    selected=[];excluded=[]
    for row in d['files']:
        parts=Path(row['path']).parts
        reason=None
        if row['root']=='pds_resouce' and any(x.startswith(('5_Software','8_嵌入式')) for x in parts):reason='vendor software installer/embedded SDK, not FPGA project artifacts'
        if row['root']=='pds_resouce' and Path(row['path']).name=='Embedded.zip':reason='embedded software SDK unrelated to image-correction project'
        if Path(row['path']).suffix.lower() in {'.exe','.msi','.dll','.pyd','.whl','.cab','.cat','.sys'}:reason='third-party tool/driver runtime binary; original project scripts and verification receipts retained'
        if any(x in {'tools_v12','tools_tmp_v12','yosys40','wheels_v12','host_validation_deps','pip_cache','pip_tmp','node_modules','__pycache__'} for x in parts):reason='third-party dependency/cache directory'
        if reason:excluded.append({**row,'reason':reason})
        else:selected.append(row)
    # Recover a Windows long-path entry reported by the initial normal-path scan.
    for error in d['errors']:
        try:
            p=error['path'];st=os.stat(native(p))
            selected.append({'path':p,'root':'workspace','rel':str(Path(p).relative_to(Path('C:/Users/叶翔/Documents/Codex/2026-10-10/x20'))).replace('\\','/'),'size':st.st_size,'mtime_ns':st.st_mtime_ns})
        except OSError:pass
    # Original videos supplied in this project, never unrelated chat media.
    ids='5117796803c5c4df9d855ec3a1d3258b 2267e3125432786606c528881df5271e 9effd484d4f80eb8f5440a45b38b4ec4 c65c83f9123b874941ca8f87cdc62ed1 53152e3caa1f542e457751b000570786 06c9ed8212056e6f1bcd310993d5bac9 ba20df72d9b46cb3a3d14ec89e9494af'.split()
    for stem in ids:
        p=Path('C:/Users/叶翔/xwechat_files/wxid_qanrp2aqlq8h22_bb90/msg/video/2026-10')/(stem+'.mp4')
        if p.exists():
            st=p.stat();selected.append({'path':str(p),'root':'original_project_videos','rel':p.name,'size':st.st_size,'mtime_ns':st.st_mtime_ns})
    # Hash once per path; every duplicate content remains represented by a path alias.
    seen=set();selected=[r for r in selected if not (os.path.normcase(r['path']) in seen or seen.add(os.path.normcase(r['path'])))]
    print('HASH files='+str(len(selected))+' bytes='+str(sum(r['size'] for r in selected)),flush=True)
    output=HERE/'hashed_files.jsonl'
    existing={}
    if output.exists():
        for line in output.read_text(encoding='utf-8').splitlines():
            try:
                row=json.loads(line)
                if 'error' not in row:existing[row['path']]=row
            except ValueError:pass
    todo=[r for r in selected if not (r['path'] in existing and all(r[k]==existing[r['path']][k] for k in ['size','mtime_ns']))]
    with output.open('a',encoding='utf-8') as f,concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for count,row in enumerate(pool.map(hashes,todo),1):
            f.write(json.dumps(row,ensure_ascii=False)+'\n')
            if count%5000==0:f.flush();print('HASHED '+str(count)+'/'+str(len(todo)),flush=True)
    (HERE/'filtered_exclusions.json').write_text(json.dumps({'scan_exclusions':d['exclusions'],'file_exclusions':excluded},ensure_ascii=False,indent=2),encoding='utf-8')
    latest={}
    for line in output.read_text(encoding='utf-8').splitlines():
        row=json.loads(line);latest[row['path']]=row
    grouped={};errors=[]
    for row in selected:
        h=latest[row['path']]
        if 'error' in h:errors.append(h);continue
        obj=grouped.setdefault(h['sha256'],{'size':h['size'],'git_blob':h['git_blob'],'paths':[]})
        obj['paths'].append({k:h[k] for k in ['path','root','rel','mtime_ns']})
    result={'objects':grouped,'errors':errors,'selected_files':len(selected),'excluded_files':len(excluded),'original_total_bytes':sum(r['size'] for r in selected),'unique_bytes':sum(o['size'] for o in grouped.values())}
    (HERE/'local_objects.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='objects'},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
