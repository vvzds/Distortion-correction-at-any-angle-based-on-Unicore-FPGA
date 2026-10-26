"""Offline evidence checks; no UART or FPGA modifications."""
from pathlib import Path
import hashlib, json, sys
sys.path.insert(0, str(Path(__file__).parents[1]/'host_validation_deps'))
import cv2
import numpy as np

ROOT=Path('C:/Users/叶翔/Desktop/yx/G7_C22_seed7真实板测_二号_20261026')
out=Path(__file__).parent/'offline_analysis.json'
base=ROOT/'02_affine_220950'
images={name:cv2.imdecode(np.fromfile(str(base/(name+'.png')),np.uint8),cv2.IMREAD_GRAYSCALE)
        for name in ['affine_plus24','affine_minus24','real_restored']}
results=[]
for a,b,expected in [('affine_plus24','affine_minus24',48),('real_restored','affine_plus24',-24),('real_restored','affine_minus24',24)]:
    # Match the fixed, non-periodic room/book scene on the right; avoid checker aliases.
    mask=np.zeros_like(images[a]);mask[100:1000,1320:1880]=255
    orb=cv2.ORB_create(nfeatures=6000)
    ka,da=orb.detectAndCompute(images[a],mask)
    kb,db=orb.detectAndCompute(images[b],None)
    pairs=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da,db,k=2)
    good=[m for m,n in pairs if m.distance<.70*n.distance]
    pa=np.float32([ka[m.queryIdx].pt for m in good]);pb=np.float32([kb[m.trainIdx].pt for m in good])
    M,inliers=cv2.estimateAffinePartial2D(pa,pb,method=cv2.RANSAC,ransacReprojThreshold=2,maxIters=5000)
    take=inliers.ravel().astype(bool)
    delta=pb[take]-pa[take]
    med=np.median(delta,axis=0)
    results.append(dict(source=a,target=b,expected_image_dx_px=expected,
                        matches=len(good),inliers=int(take.sum()),median_dx_dy=med.tolist(),
                        median_residual_px=float(np.median(np.linalg.norm(delta-med,axis=1))),
                        affine_fit=M.tolist(),
                        verified=False,
                        note='Inconclusive: too few consistent inliers and scene movement; do not use as proof of affine effect'))

# Independent double-precision Brown mapping: row-request locality diagnostic only.
# This deliberately does not model RTL rounding, prefetch, DDR grant latency or cycles.
fx,fy,cx,cy=1507.710442199695,1507.403518870939,883.533081692948,568.687748120301
k1,k2,p1,p2=-.381482584692,.156698401312,-.000303016236,-.000110983241
x=(np.arange(1920)-cx)/fx
loads=0;tags=[-1]*4;cursor=0;row_span=[];per_line=[]
for v in range(1079,-1,-1):
    y=(v-cy)/fy;r2=x*x+y*y
    sy=np.clip(fy*(y*(1+k1*r2+k2*r2*r2)+p1*(r2+2*y*y)+2*p2*x*y)+cy,0,1079)
    row=1079-np.floor(sy).astype(int)
    row_span.append(int(row.max()-row.min()+1))
    # Consecutive identical row pairs have no intervening misses; collapse them.
    runs=np.r_[True,row[1:]!=row[:-1]]
    before=loads
    for a in row[runs]:
        a=int(a);b=max(0,a-1)
        while a not in tags or b not in tags:
            ha=a in tags;hb=b in tags
            target=b if ha else a
            victim=cursor
            if ha and not hb and tags[victim]==a: victim=(victim+1)%4
            elif not ha and hb and tags[victim]==b: victim=(victim+1)%4
            tags[victim]=target;cursor=(victim+1)%4;loads+=1
    per_line.append(loads-before)
result=dict(affine_image_checks=results,
            locality_diagnostic=dict(model='Independent float Brown map, 4 resident full source rows, round robin demand loading',
                source_row_span_per_output_line_max=max(row_span),
                source_row_span_per_output_line_mean=float(np.mean(row_span)),
                estimated_line_loads_per_frame=loads,estimated_line_loads_per_output_line_mean=float(np.mean(per_line)),
                caveat='Not bit exact or cycle accurate. Cannot alone prove the cause of measured 4fps.'),
            image_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.glob('*.png')})
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(out)
print(json.dumps(result,ensure_ascii=False,indent=2))
