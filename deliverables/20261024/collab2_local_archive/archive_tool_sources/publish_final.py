"""Publish the complete archive after all payload batches, retaining source history."""
from pathlib import Path
import sys,subprocess,json,time,shutil,hashlib
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'github_repository_setup_20261024'))
from repo_git import GIT,environment
REPO=Path('C:/Users/叶翔/Documents/Codex/fpga-main')
REL=Path('deliverables/20261024/collab2_local_archive')
BASE=REPO/REL
DESKTOP=Path('C:/Users/叶翔/Desktop/yx/本机项目全量归档上传_二号_20261024')
BRANCH='collab2/local-complete-archive-20261024'
env=environment()
def git(*args,timeout=600,check=True):
    p=subprocess.run([str(GIT),'-C',str(REPO),*args],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if check and p.returncode:raise RuntimeError((p.stderr+p.stdout).decode('utf-8','replace')[-3000:])
    return p
def out(*args):return git(*args).stdout.decode('utf-8','replace').strip()

def main():
    assert out('branch','--show-current')==BRANCH
    manifest=json.loads((BASE/'MANIFEST.json').read_text(encoding='utf-8'))
    tracked=set(out('ls-files','--',str(REL/'packs').replace('\\','/')).splitlines())
    assert all((REL/p['path']).as_posix() in tracked for p in manifest['packs']),'Payload batch not yet committed'
    assert json.loads((BASE/'VERIFICATION.json').read_text(encoding='utf-8'))['state']=='PASS'
    # Assert the current pushed batch tip exists, so final publication cannot
    # accidentally send a >2GB unbounded push after an interrupted batch run.
    remote_tip=out('ls-remote','--heads','origin',BRANCH).split()[0]
    assert remote_tip==out('rev-parse','HEAD'),'Last batch has not been pushed'
    before=manifest['source_commits']['origin/main']
    core_paths=['source','ipcore','sim','HDMI_DDR3_OV5640_test.fdc','task1_1080p30.pds']
    core_comparison={path:{'before':out('rev-parse',before+':'+path),'current':out('rev-parse','HEAD:'+path)} for path in core_paths}
    (BASE/'REPOSITORY_INTEGRATION.json').write_text(json.dumps({'original_main':before,'source_subtrees':core_comparison,'all_current_production_inputs_unchanged':all(x['before']==x['current'] for x in core_comparison.values()),'policy':'Versioned artifacts, latest-version entry index, and Git merge history; no mixing of unrelated core/gate/production variants.'},ensure_ascii=False,indent=2),encoding='utf-8')
    # Refresh small-file checksums and the Desktop copy after the integration receipt.
    result=subprocess.run([sys.executable,str(HERE/'finalize_docs.py')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf-8','replace'))
    verification=subprocess.run([sys.executable,str(BASE/'verify_downloaded_archive.py')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if verification.returncode:raise RuntimeError(verification.stderr.decode('utf-8','replace'))
    print(verification.stdout.decode('utf-8','replace').strip(),flush=True)
    git('add','-f','--',REL.as_posix(),'README.md')
    git('diff','--cached','--check')
    git('commit','-m','Index complete collaborator 02 local archive, historical versions, and verified restore tools')
    print('FINAL METADATA COMMITTED',flush=True)
    git('fetch','origin','+refs/heads/*:refs/remotes/origin/*')
    for ref in ['origin/main','origin/contributor-01/materials-20261024']:
        git('merge','--no-edit','--no-stat',ref)
    # Recompare against any collaborator updates made while the large payload
    # was uploading, then refresh the highest-version index before publication.
    current_remote={ref:out('rev-parse',ref) for ref in manifest['source_commits']}
    if current_remote!=manifest['source_commits']:
        info=json.loads((BASE/'REPOSITORY_INTEGRATION.json').read_text(encoding='utf-8'))
        info['source_subtrees']={path:{'before':out('rev-parse',before+':'+path),'current':out('rev-parse','HEAD:'+path)} for path in core_paths}
        info['all_current_production_inputs_unchanged']=all(x['before']==x['current'] for x in info['source_subtrees'].values())
        info['latest_collaborator_commits']=current_remote
        (BASE/'REPOSITORY_INTEGRATION.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
        for name in ['prepare_remote.py','finalize_docs.py']:
            p=subprocess.run([sys.executable,str(HERE/name)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace'))
        git('add','-f','--',REL.as_posix(),'README.md')
        if git('diff','--cached','--quiet',check=False).returncode:
            git('commit','-m','Refresh archive version index against latest collaborator branches')
    tag='archive/main-before-collab2-full-sync-20261024'
    if git('rev-parse','--verify',tag,check=False).returncode:
        git('tag','-a',tag,before,'-m','Preserve management main before collaborator 02 complete local archive integration')
    assert out('rev-list','-1',tag)==before
    head=out('rev-parse','HEAD')
    print('PUBLISH '+head,flush=True)
    push=git('push','--atomic','origin','HEAD:refs/heads/'+BRANCH,'HEAD:refs/heads/main','refs/tags/'+tag,timeout=900,check=False)
    main_published=push.returncode==0
    pr=None
    if not main_published:
        reason=push.stderr.decode('utf-8','replace')[-2000:]
        print('MAIN DIRECT PUSH NOT ACCEPTED: '+reason,flush=True)
        git('push','origin','HEAD:refs/heads/'+BRANCH,'refs/tags/'+tag,timeout=900)
        gh=HERE.parent/'github_repository_setup_20261024/tools/gh.exe'
        body=HERE/'pr_body.md'
        body.write_text('本机项目资料、全部历史工程和证据已按内容去重归档，提供版本索引与逐文件SHA256恢复工具。已并入一号资料分支，保留原分支与旧版Git提交。\n\n主归档包含188336条文件路径、14518份不重复内容、65个载荷分片（约2.86GB），另有M01源文件及原始附件补充。逐对象重建、全部归档校验和旧版恢复测试通过。\n\n未进行板卡烧录或UART写入；G4 1080p30/125MHz时序候选仍待实机验收。',encoding='utf-8')
        p=subprocess.run([str(gh),'pr','create','--repo','vvzds/Distortion-correction-at-any-angle-based-on-Unicore-FPGA','--base','main','--head',BRANCH,'--title','归档二号本机全部项目工程、资料和历史数据','--body-file',str(body)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if p.returncode:raise RuntimeError(p.stderr.decode('utf-8','replace'))
        pr=p.stdout.decode().strip()
    refs=out('ls-remote','--heads','origin','main',BRANCH)
    heads={line.split()[1]:line.split()[0] for line in refs.splitlines()}
    assert heads['refs/heads/'+BRANCH]==head
    if main_published:assert heads['refs/heads/main']==head
    receipt={'state':'UPLOADED_MAIN' if main_published else 'UPLOADED_BRANCH_PR_PENDING','finished':time.strftime('%Y-%m-%dT%H:%M:%S'),'repository':'https://github.com/vvzds/Distortion-correction-at-any-angle-based-on-Unicore-FPGA','branch':BRANCH,'commit':head,'remote_heads':heads,'old_main_tag':tag,'original_main':before,'main_published':main_published,'pull_request':pr,'summary':json.loads((BASE/'SUMMARY.json').read_text(encoding='utf-8')),'archive_sha256_manifest':hashlib.sha256((BASE/'SHA256SUMS.txt').read_bytes()).hexdigest(),'recipients':['管理方/执行者','一号协作者','二号协作者'],'scope':'All inventoried FPGA project files plus M01/report/media/standalone supplements; software installers, runtimes/caches, credentials, and unrelated personal files excluded.'}
    for path in [HERE/'final_upload_receipt.json',DESKTOP/'02_仓库上传回执.json']:
        path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
