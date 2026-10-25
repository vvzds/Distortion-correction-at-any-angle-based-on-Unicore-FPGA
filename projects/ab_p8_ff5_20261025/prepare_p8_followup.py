from pathlib import Path
import hashlib,shutil
R=Path(r'C:\Users\lenovo\Desktop\ww\AB_P8触摸译码局部化_20261025')
sha=hashlib.sha256((R/'candidate/source/rtl/undistort_cache_ab.v').read_bytes()).hexdigest()
p=R/'compare_regression.py';s=p.read_text(encoding='utf-8').replace('b2042db9c8d40dafb4c277104d909a76caca140d57e2c549bf1d7665324678c3',sha);p.write_text(s,encoding='utf-8')
p=R/'run_full_regression.py';s=p.read_text(encoding='utf-8').replace('len(negative)==18','len(negative)==22');p.write_text(s,encoding='utf-8')
shutil.copy2(__file__,R/'prepare_p8_followup.py')
