from pathlib import Path
import os,json,hashlib,shutil
HERE=Path(__file__).resolve().parent
BASE=Path('C:/Users/叶翔/Documents/Codex/fpga-main/deliverables/20261024/collab2_local_archive')
stems='''73d0a809244ebbcf1103f821cae39481 f88837dd266f473da1b89550ab4da36d 465c60bfdb4e73164dce8f8dff4e3732 b45bb6738dc98bd849cf425ff67c7243 5d4bd334db5d6132cc1c5871117f6009 2f6620ffd7cb56aee6ec38966d99a2f5 40d3efaf841e6278be053af693b6d905 1b31ff6f4080da3b4d17850ba93ee188 581be558d68acd63c4f0ad3e4149fa09 1046d8a2ca60cfac8d40b9dc5e9a07a8 a5432853dc7cb45f4028a0ff8325f447 db73fddc090af922891fb479008ef092 fe3355b9bf0e0961ac9f9f2d66982ce7 b174e531ae76609373984b0aa79a197c 5b77d290db9693f78b62751bc34dddd1 d1f7662a1a57c1a409c2827bdbf33d74 cbbb71f17661a1d8e95557c589bb7228 47988197c258b545c271cb3ed3bd5f4f 4f244f8b17c36419816da9b5bbd90e6c 98504953212d34b88b7962fd6769562c 33433ae104d629cb2a18f52aa4738f1c 48eaf4ad60dbe38b7a2f7da8181f6467 e09a27854a79a7587c7e55f0c449fbd8 1dc0fc333c5abb87b9f683f425352f03 ee6e3795377fc95a86443e422c4e06a7 46f1c0b041507f9e6f2b98e32a39a48e codex-clipboard-522b1084-8c2d-4fd3-ab59-734d7eccf804 codex-clipboard-d112ea3f-33de-466f-ac8a-b33bf86dfaee codex-clipboard-c72f51ee-1ce7-4bfc-9ebd-8a6f1a4e56df codex-clipboard-de3a36ec-51ac-4e28-acfb-fc2478d187cc codex-clipboard-f0dda44e-82c9-49a9-8443-7e7c34f23769 codex-clipboard-35026470-fde1-471c-8df6-d0a1c5cee3e7 codex-clipboard-db721f17-cfdb-4004-b7e7-ba139a53ab1c codex-clipboard-345bd8db-6e6c-43e9-8f09-b6d24603d7be codex-clipboard-9e10b587-6a38-4e65-a437-330444e95922 codex-clipboard-fbf1d6c6-6eaa-4b98-bc5e-6f078818f3aa codex-clipboard-1bd12681-8e36-408d-8c99-095c7bccb083'''.split()
wanted=set(stems);found=[]
roots=[Path('C:/Users/叶翔/xwechat_files/wxid_qanrp2aqlq8h22_bb90/temp/RWTemp/2026-10'),Path('C:/Users/叶翔/AppData/Local/Temp')]
target=BASE/'original_project_images';target.mkdir(exist_ok=True)
for root in roots:
    if not root.exists():continue
    for base,dirs,files in os.walk(root):
        if root.name=='Temp':dirs[:]=[]
        for name in files:
            p=Path(base)/name
            if p.stem not in wanted:continue
            raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest();dst=target/name
            if dst.exists() and hashlib.sha256(dst.read_bytes()).hexdigest()!=sha:dst=target/(sha[:8]+'_'+name)
            dst.write_bytes(raw)
            found.append({'source':str(p),'path':dst.relative_to(BASE).as_posix(),'bytes':len(raw),'sha256':sha})
(BASE/'ORIGINAL_IMAGES.json').write_text(json.dumps({'files':found,'not_present_locally':sorted(wanted-{Path(x['source']).stem for x in found})},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'original_images':len(found),'not_present_locally':len(wanted-{Path(x['source']).stem for x in found})}))
