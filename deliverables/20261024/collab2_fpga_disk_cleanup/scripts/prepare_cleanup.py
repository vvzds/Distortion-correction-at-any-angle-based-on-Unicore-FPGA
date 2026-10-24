from pathlib import Path
import os,json,gzip,hashlib,subprocess,importlib.util,time
W=Path(__file__).resolve().parent
work=W.parent
repo=Path('C:/Users/叶翔/Documents/Codex/fpga-main')
archive=repo/'deliverables/20261024/collab2_local_archive'
git='C:/Users/叶翔/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def key(p):return os.path.normcase(os.path.abspath(p))
with gzip.open(archive/'PATHS.jsonl.gz','rt',encoding='utf-8') as f:
    aliases={key(r['path']):r for r in map(json.loads,f)}
targets=[]
for folder,subs in {
    'G8_receipt_review_20261024':['received','delivery'],
    'G7_R01_R14_followup_20261023':['received','release','delivery'],
    'outsourced_audit_20261024':['received','delivery'],
    'V204_intake_independent_20261023':['received'],
    'AB_M01_intake_compare_20261023':['received'],
    'G6_PAP_GROUP_review_20261023':['archive_cli_replay','G6_PAP_GROUP_binding_audit'],
}.items():
    for sub in subs:targets.append((work/folder/sub,'archived_extraction_or_delivery_copy'))
targets += [(Path('D:/FPGA PDS/yx')/sub,'superseded_static_build_attempt') for sub in ['static_G4_bringup_20261024','static_G4_timing_resume_20261024']]
duplicate=Path('C:/Users/叶翔/Desktop/yx/本机项目全量归档上传_二号_20261024/完整归档')
targets.append((duplicate,'duplicate_archive_copy'))
targets += [(work/'pds_sp64_setup'/n,'unused_SP64_install_payload') for n in ['Setup.exe','payload_extract_only.nsis']]
planned=[];skipped=[]
observed_previous_hash_pass={
    key(work/a/b) for a,b in [
        ('G8_receipt_review_20261024','received'),('G8_receipt_review_20261024','delivery'),
        ('G7_R01_R14_followup_20261023','received'),('G7_R01_R14_followup_20261023','release'),
        ('outsourced_audit_20261024','received'),('outsourced_audit_20261024','delivery'),
        ('V204_intake_independent_20261023','received')]
}
# These complete hash passes were observed in the preceding run's stdout. That run
# failed later on a long AB_M01 path, before any deletion. Reuse only unchanged
# archive timestamps/sizes; changed metadata forces a fresh content hash.
checkpoint=W/'preflight_checkpoint.json'
if checkpoint.exists():
    saved=json.loads(checkpoint.read_text(encoding='utf-8'));planned=saved['files'];skipped=saved['skipped']
    completed=set(saved['completed'])
else:completed=set()
def persist():
    checkpoint.write_text(json.dumps({'files':planned,'skipped':skipped,'completed':sorted(completed)},ensure_ascii=False),encoding='utf-8')
for target,reason in targets:
    if str(target) in completed:continue
    if not target.exists():continue
    errors=[];files=[]
    if target.is_file():files=[target]
    else:
        for b,ds,fs in os.walk(target,followlinks=False,onerror=lambda e:errors.append(str(e))):
            for d in ds:
                p=Path(b,d)
                try:
                    if p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400:errors.append('Reparse: '+str(p))
                except OSError as e:errors.append(str(e))
            files += [Path(b,f) for f in fs]
    if errors:
        skipped.append({'target':str(target),'reason':'scan incomplete','errors':errors});completed.add(str(target));persist();continue
    batch=[];bad=[]
    for p in files:
        try:
            if p.is_symlink() or getattr(p.stat(),'st_file_attributes',0)&0x400:bad.append(str(p));continue
            s=p.stat();a=aliases.get(key(p))
            if key(target) in observed_previous_hash_pass and a and s.st_size==a['size'] and s.st_mtime_ns==a['mtime_ns']:
                h=a['sha256']
            else:h=sha(p)
        except OSError:
            bad.append(str(p));continue
        entry={'path':str(p.resolve()),'bytes':s.st_size,'sha256':h,'mtime_ns':s.st_mtime_ns,'reason':reason,'target':str(target.resolve())}
        if reason=='unused_SP64_install_payload':entry['recovery']='Disposable installer only; installed PDS preserved'
        elif reason=='duplicate_archive_copy':
            keep=archive/p.relative_to(target)
            if not keep.is_file() or sha(keep)!=h:bad.append(str(p));continue
            entry['keep_path']=str(keep)
        else:
            a=aliases.get(key(p))
            if not a or a['sha256']!=h:bad.append(str(p));continue
            entry['archive']={'root':a['root'],'rel':a['rel'],'object_sha256':h}
        batch.append(entry)
    if bad:
        skipped.append({'target':str(target),'reason':'not fully backed up or changed','files':bad});completed.add(str(target));persist();continue
    planned.extend(batch)
    completed.add(str(target));persist()
    print('VERIFIED',round(sum(x['bytes'] for x in batch)/1024**3,3),'GiB',target,flush=True)
(W/'plan.json').write_text(json.dumps({'created':time.strftime('%Y-%m-%dT%H:%M:%S'),'targets':[str(p.resolve()) for p,_ in targets], 'files':planned,'skipped':skipped},ensure_ascii=False,indent=2),encoding='utf-8')
print('PLANNED',len(planned),'files',sum(x['bytes'] for x in planned)/1024**3,'GiB; skipped',len(skipped),flush=True)

# Verify recovery bytes for every distinct object used by the deletion plan.
spec=importlib.util.spec_from_file_location('archive_restore',archive/'restore_archive.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
auth_spec=importlib.util.spec_from_file_location('git_transport',work/'github_repository_setup_20261024/repo_git.py')
auth=importlib.util.module_from_spec(auth_spec);auth_spec.loader.exec_module(auth)
git_env=dict(auth.environment(),GIT_NO_LAZY_FETCH='1')
local_objects={}
listing=subprocess.check_output([git,'-C',str(repo),'cat-file','--batch-all-objects','--batch-check=%(objectname) %(objectsize)'],env=git_env,timeout=30)
for line in listing.splitlines():
    oid,size=line.split();local_objects[oid.decode()]=int(size)
def git_stream(oid):
    if oid not in local_objects:raise ValueError('Git backup not cached locally; preserve source')
    size=local_objects[oid]
    proc=subprocess.Popen([git,'-C',str(repo),'cat-file','blob',oid],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=git_env)
    digest=hashlib.sha1(b'blob '+str(size).encode()+b'\0');count=0
    for block in iter(lambda:proc.stdout.read(4*1024**2),b''):
        digest.update(block);count+=len(block);yield block
    proc.stdout.close();err=proc.stderr.read();proc.stderr.close()
    if proc.wait()!=0 or count!=size or digest.hexdigest()!=oid:raise ValueError('Git restore stream failed '+oid)
reader=m.Reader(archive,repo,git,remote_reader=git_stream)
objects={x['sha256'] for x in planned if 'archive' in x}
verified=[];retained={};failed={}
progress_path=W/'recovery_progress.json'
if progress_path.exists():
    progress=json.loads(progress_path.read_text(encoding='utf-8'))
    verified=progress['verified'];retained=progress['retained'];failed=progress['failed']
already=set(verified)|set(failed)
local_candidates=json.loads((W/'retained_git_candidates.json').read_text(encoding='utf-8'))
try:
    for i,h in enumerate(sorted(objects)):
        if h in already:continue
        try:
            candidate=Path(local_candidates[h]) if h in local_candidates else None
            if candidate and sha(candidate)==h:
                retained[h]=str(candidate);verified.append(h)
            else:
                # No network is required to prove local restoration. Preserve any
                # source whose Git backup is not already locally available.
                obj=reader.manifest['objects'][h]
                if obj['storage']['kind'] in ('git','git_concat'):
                    oids=[obj['storage']['oid']] if obj['storage']['kind']=='git' else [p['oid'] for p in obj['storage']['parts']]
                    for oid in oids:
                        if oid not in local_objects:raise ValueError('Git backup not cached locally; preserve source')
                digest=hashlib.sha256();size=0
                for b in reader.stream(h):digest.update(b);size+=len(b)
                if digest.hexdigest()!=h or size!=reader.manifest['objects'][h]['size']:raise ValueError('Recovery mismatch '+h)
                verified.append(h)
        except Exception as e:failed[h]=str(e)
        if (i+1)%250==0:
            print('RESTORE CONTENT CHECK',i+1,'/',len(objects),'preserve',len(failed),flush=True)
            (W/'recovery_progress.json').write_text(json.dumps({'verified':verified,'retained':retained,'failed':failed}),encoding='utf-8')
finally:reader.close()
# A target is retained in full if even one recovery object cannot be verified.
bad_targets={x['target'] for x in planned if x['sha256'] in failed}
planned=[x for x in planned if x['target'] not in bad_targets]
for target in bad_targets:skipped.append({'target':target,'reason':'local recovery not fully verified; retained whole directory'})
for entry in planned:
    if entry['sha256'] in retained:entry['keep_path']=retained[entry['sha256']]
(W/'plan.json').write_text(json.dumps({'created':time.strftime('%Y-%m-%dT%H:%M:%S'),'targets':[str(p.resolve()) for p,_ in targets],'files':planned,'skipped':skipped},ensure_ascii=False,indent=2),encoding='utf-8')
(W/'recovery_verification.json').write_text(json.dumps({'status':'PASS','objects':verified,'retained_equivalent_files':retained,'unverified_preserved_objects':failed,'plan_sha256':sha(W/'plan.json'),'archive_manifest_sha256':sha(archive/'MANIFEST.json')},indent=2),encoding='utf-8')
print('ALL PLANNED ARCHIVE OBJECTS RECOVERABLE',len(verified),flush=True)
