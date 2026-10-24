"""Bundle the actual supplementary run and recipient-specific review inputs."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, shutil, zipfile

ROOT=Path(__file__).resolve().parent
WW=ROOT.parent
AB=WW/'AB_independent_20261023'
OUT=WW/'待转交'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def bundle(path,prefix,files):
    if path.exists():raise FileExistsError('Preserve prior delivery: '+str(path))
    manifest=[dict(file=k,bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for k,v in sorted(files.items())]
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for k,v in sorted(files.items()):z.writestr(prefix+'/'+k,v)
        z.writestr(prefix+'/files_sha256.json',json.dumps(manifest,ensure_ascii=False,indent=2).encode('utf-8'))
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:raise RuntimeError('CRC failed')
        if len(z.namelist())!=len(manifest)+1:raise RuntimeError('coverage failed')
        for x in manifest:
            data=z.read(prefix+'/'+x['file'])
            if len(data)!=x['bytes'] or hashlib.sha256(data).hexdigest()!=x['sha256']:raise RuntimeError('SHA failed')
    return dict(file=path.name,bytes=path.stat().st_size,sha256=sha(path),entries=len(manifest)+1,status='CRC_ALL_FILE_SHA256_PASS')

def main():
    reference=ROOT/'reference';reference.mkdir(exist_ok=True)
    src=AB/'core/source/rtl/undistort_map.v'
    frozen='aafbaac6f658c0f7ea6219bcb172a05f82b836ac1275651d1a0aec29251a9ee3'
    if sha(src)!=frozen:raise RuntimeError('frozen map changed')
    shutil.copyfile(src,reference/'undistort_map.v')
    b=json.loads((ROOT/'evidence/baseline_01/result.json').read_text(encoding='utf-8'))
    n=json.loads((ROOT/'evidence/negative_01/summary.json').read_text(encoding='utf-8'))
    if b['status']!='PASS' or n['status']!='PASS':raise RuntimeError('probe run failed')
    common={'本轮分发说明.md':(WW/'本轮分发说明_20261024.md').read_bytes(),
            '待协作者统一提供材料清单.md':(AB/'docs/待协作者统一提供材料清单.md').read_bytes(),
            'verify_package.py':(AB/'tools/verify_package.py').read_bytes()}
    second=dict(common)
    second['README_给二号.md']='''# 二号本轮入口

先读本轮分发说明.md和map_probe/README.md。map_probe/为新做出的接口探针及正负例原始证据；prior_review/内是同日原审查ZIP，整体哈希保持不变，可独立解压复核，不必再索取另一份旧审查包。新核心仍未收到，本包不构成新核心验收。

请按N01–N04回传实际新优化包与证据。探针只针对单文件map的选定接口语义，完整core/cache依赖须另列，不以通过探针替代全帧/数值/时序门禁。
'''.encode('utf-8')
    for p in ROOT.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            second['map_probe/'+p.relative_to(ROOT).as_posix()]=p.read_bytes()
    prior=OUT/'给二号及设计方_独立进展T02合并与材料清单_20261024.zip'
    expected='b31cab7e7dadbee5426d99032b7d352be3b29d8d0a5e165a2a0c33408e47552a'
    if sha(prior)!=expected:raise RuntimeError('prior review identity mismatch')
    second['prior_review/'+prior.name]=prior.read_bytes()
    designer=dict(common)
    designer['README_给设计方.md']='''# 设计方本轮入口

先读本轮分发说明.md。T02/含整理稿、diff和裁定原件，D01仅审阅归档；docs/综合报告与evidence/警告/原日志用于E02–E04处理依据。map_probe报告是新增独立实测，不是修改冻结周期的提案。

本包为审查资料，不含全量RTL/IP及综合数据库；原receipt里的源码/数据库路径对应“给执行方_AB新哈希综合证据与物理评估输入_20261024.zip”。不在精简包中重放固定输入复核。请就UART真实连线/电气、PNR测量边界及范围、FBG484 IP/FBG676工程适用性、共享引脚/旧调试网/综合诊断给出具体依据或处理方案；本方未擅自改FDC/RTL来压掉诊断。

最终网表W01和新核心N01–N04尚缺。板端B01–B03暂停，不要求目前补旧G4实拍。
'''.encode('utf-8')
    for folder in ('T02',):
        for p in (AB/folder).rglob('*'):
            if p.is_file():designer[p.relative_to(AB).as_posix()]=p.read_bytes()
    for name in ('AB新哈希综合与独立任务交付报告.md','AB执行方SOP.md','新优化核心接入前检查.md'):
        designer['docs/'+name]=(AB/'docs'/name).read_bytes()
    for kind in ('core','host'):
        for name in ('console.log','process_receipt.json','fixed_input_audit.json','warning_lines.txt'):
            p=AB/'evidence'/('synth_'+kind)/name
            designer[p.relative_to(AB).as_posix()]=p.read_bytes()
        for p in (AB/kind/'synthesize').glob('*.snr'):
            designer[p.relative_to(AB).as_posix()]=p.read_bytes()
    designer['evidence/warning_index.json']=(AB/'evidence/warning_index.json').read_bytes()
    designer['map_probe_接口实测报告.md']=(ROOT/'README.md').read_bytes()
    designer['map_probe_baseline_result.json']=(ROOT/'evidence/baseline_01/result.json').read_bytes()
    result=[bundle(OUT/'给二号_新核心接入探针与审查资料_20261024.zip','collab2_supplement_20261024',second),
            bundle(OUT/'给设计方_T02归档与物理前置问题_20261024.zip','designer_review_20261024',designer)]
    receipt=dict(date='2026-10-24',generated_utc=datetime.now(timezone.utc).isoformat(),packages=result,
                 frozen_map_unchanged=sha(src)==frozen,
                 executor_package_unchanged=sha(OUT/'给执行方_AB新哈希综合证据与物理评估输入_20261024.zip')=='0dbfe42cd5aeaa9d88a972013a88de20bd451b2a66fee197448da2029f6f2dba')
    (OUT/'补充分发核验_20261024.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'补充分发_SHA256SUMS.txt').write_text(''.join(x['sha256']+'  '+x['file']+'\n' for x in result),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
