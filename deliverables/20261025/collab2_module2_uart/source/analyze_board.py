"""实机原图独立分析；不把软件变换图用作板端校正结果。"""
from pathlib import Path
import hashlib,json,struct,sys
W=Path(__file__).resolve().parent
sys.path.insert(0,str(W.parent/'host_validation_deps'))
import cv2,numpy as np
cv2.ocl.setUseOpenCL(False);cv2.setNumThreads(2)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def aligned(points,target):
    g=np.asarray(points).reshape(8,11,2)
    candidates=[g,g[::-1],g[:,::-1],g[::-1,::-1]]
    return min((c.reshape(-1,2) for c in candidates),key=lambda c:np.mean(np.linalg.norm(c-target,axis=1)))

def line_rms(p):
    g=np.asarray(p).reshape(8,11,2);lines=list(g)+list(g.transpose(1,0,2));r=[]
    for a in lines:
        c=a-a.mean(axis=0);_,_,vh=np.linalg.svd(c,full_matrices=False)
        r.append(float(np.sqrt(np.mean((c@vh[1])**2))))
    return float(np.mean(r))

def rms2(v):return float(np.sqrt(np.mean(np.sum(v*v,axis=-1))))

def analyze(folder):
    result=json.loads((folder/'result.json').read_text(encoding='utf-8'))
    assert result['state']=='CAPTURE_SEQUENCE_COMPLETED_ANALYSIS_REQUIRED' and not result['errors']
    out=folder/'analysis';out.mkdir(exist_ok=True)
    groups={};images={};rows=[];tiles=[]
    for stage in result['stages']:
        name=stage['name'];groups[name]=[];images[name]=[]
        for i,f in enumerate(stage['captures']):
            p=Path(f['path']);assert sha(p)==f['sha256']
            img=cv2.imdecode(np.frombuffer(p.read_bytes(),np.uint8),cv2.IMREAD_COLOR)
            gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
            found,c=cv2.findChessboardCornersSB(gray,(11,8),cv2.CALIB_CB_NORMALIZE_IMAGE)
            row=dict(stage=name,capture=i,path=str(p),sha256=f['sha256'],corners88=bool(found))
            if found:
                a=c[:,0].astype(float)
                if groups[name]:a=aligned(a,groups[name][0])
                groups[name].append(a);row.update(corners_xy=a.tolist(),line_rms_px=line_rms(a))
                view=img.copy();cv2.drawChessboardCorners(view,(11,8),c,found)
                overlay=p.with_name(p.stem+'_corners.png');overlay.write_bytes(cv2.imencode('.png',view)[1].tobytes())
                row['overlay_path']=str(overlay)
            rows.append(row);images[name].append(img)
            if i==0:
                tile=cv2.resize(img,(640,360));cv2.rectangle(tile,(0,0),(640,28),(0,0,0),-1)
                cv2.putText(tile,name,(8,21),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1,cv2.LINE_AA);tiles.append(tile)
    metrics=dict(frame_analysis=rows,physical_acceptance='NOT_EVALUATED',parameter_values_readback='NOT_AVAILABLE_IN_FROZEN_0x05',
       limitations=['Raw frames are Hagibis MJPG decoded to PNG; not sensor RAW or lossless HDMI capture.',
       'Exposure/WB not hardware locked or read back; brightness stability is measured observationally.',
       'Internal no-mixed-parameter-frame property is RTL evidence, not directly observable from sparse captures.',
       'Only scalar 0x05 status can be read; live coefficients, affine/Gamma enable and LUT values cannot be read directly.'])
    if all(len(groups[n])==3 for n in groups):
        base=groups['real_baseline'][0]
        mean={n:np.mean([aligned(p,base) for p in g],axis=0) for n,g in groups.items()}
        std={n:float(np.max([rms2(aligned(p,base)-mean[n]) for p in g])) for n,g in groups.items()}
        identity=mean['identity'];real=mean['real_restored']
        fx,fy,cx,cy,k1,k2,p1,p2=np.asarray(struct.unpack('<8i',(W/'reference/parameters/real_0x01.bin').read_bytes()[4:-1]))/65536
        # 依照Brown4文字公式，校正输出坐标反查传感器坐标，与恒等实拍角点比。
        x=(real[:,0]-cx)/fx;y=(real[:,1]-cy)/fy;r2=x*x+y*y
        radial=1+k1*r2+k2*r2*r2
        predicted=np.stack([fx*(x*radial+2*p1*x*y+p2*(r2+2*x*x))+cx,
                            fy*(y*radial+p1*(r2+2*y*y)+2*p2*x*y)+cy],axis=1)
        shift=mean['affine_tx24']-real
        metrics['geometry']=dict(all_27_frames_have_88_corners=True,
            max_within_stage_corner_rms_px=std,
            identity_line_rms_px=float(np.mean([line_rms(p) for p in groups['identity']])),
            real_line_rms_px=float(np.mean([line_rms(p) for p in groups['real_restored']])),
            real_vs_identity_corner_rms_px=rms2(real-identity),
            brown4_reverse_map_vs_identity_corner_rms_px=rms2(predicted-identity),
            restore_baseline_corner_rms_px=rms2(real-base),
            affine_observed_median_xy_px=np.median(shift,axis=0).tolist(),
            affine_expected_xy_px=[-24,0],affine_expected_translation_error_rms_px=rms2(shift-np.array([-24,0])),
            affine_disable_restore_rms_px=rms2(mean['affine_off']-real),
            gamma_disable_restore_rms_px=rms2(mean['gamma_off']-real),
            rejected_frames_restore_rms_px=rms2(mean['rejected_frames']-mean['gamma_off']))
    else:metrics['geometry']=dict(all_27_frames_have_88_corners=False,found_counts={k:len(v) for k,v in groups.items()})
    # 仅对同几何坐标、固定棋盘白块内部取亮度，腐蚀掩膜排除边界位移噪声。
    avg={n:np.mean(g,axis=0).astype(np.float32) for n,g in images.items()}
    reference=avg['gamma_identity'];mask=np.min(reference,axis=2)>110
    mask&=np.max(reference,axis=2)<230;mask[:100]=False;mask[1000:]=False;mask[:,:350]=False;mask[:,1600:]=False
    mask=cv2.erode(mask.astype(np.uint8),np.ones((15,15),np.uint8)).astype(bool)
    assert np.count_nonzero(mask)>1000
    dim=avg['gamma_dim'];off=avg['gamma_off'];rejected=avg['rejected_frames']
    med=lambda a:[float(x) for x in np.median(a[mask],axis=0)]
    ratios=lambda a,b:[float(x) for x in np.median(a[mask]/np.maximum(b[mask],1),axis=0)]
    metrics['photometry']=dict(white_mask_pixels=int(mask.sum()),
        median_bgr={n:med(avg[n]) for n in ('affine_off','gamma_identity','gamma_dim','gamma_off','rejected_frames')},
        dim_over_identity_bgr=ratios(dim,reference),
        identity_enabled_over_bypass_bgr=ratios(reference,avg['affine_off']),
        gamma_off_over_pre_gamma_bgr=ratios(off,avg['affine_off']),
        rejected_frames_over_gamma_off_bgr=ratios(rejected,off),
        note='Ratios are decoded HDMI observations; do not compare directly to LUT 0.60 as exact radiometry (RGB565, HDMI/card range).')
    # 工程证据阈值与竞赛验收分开；阈值在代码明示。
    g=metrics['geometry'];p=metrics['photometry']
    checks={
      'all_stages_publishing':all(s['fresh_publications_at_least']>=3 for s in result['stages']),
      'restore_publishing':result['restoration'].get('verified_publishing',False),
      'all_frames_88_corners':g.get('all_27_frames_have_88_corners',False),
      'brown4_observable_and_model_consistent':g.get('real_vs_identity_corner_rms_px',0)>3 and g.get('brown4_reverse_map_vs_identity_corner_rms_px',1e9)<3,
      'affine_observable_24px':g.get('affine_expected_translation_error_rms_px',1e9)<2,
      'geometric_restore':max(g.get(k,1e9) for k in ('restore_baseline_corner_rms_px','affine_disable_restore_rms_px','gamma_disable_restore_rms_px','rejected_frames_restore_rms_px'))<2,
      'gamma_identity_approximately_bypass':all(.90<v<1.10 for v in p['identity_enabled_over_bypass_bgr']),
      'gamma_dimming_observable':all(.35<v<.85 for v in p['dim_over_identity_bgr']),
      'gamma_disable_restores':all(.90<v<1.10 for v in p['gamma_off_over_pre_gamma_bgr']),
      'bad_frames_no_observed_mode_change':all(.95<v<1.05 for v in p['rejected_frames_over_gamma_off_bgr'])}
    metrics['engineering_checks']=checks
    metrics['state']='ENGINEERING_OBSERVATIONS_PASS' if all(checks.values()) else 'ENGINEERING_REVIEW_REQUIRED'
    metrics['note']='Engineering thresholds check visible command effects; not competition image quality or full frame atomicity certification.'
    (out/'metrics.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),encoding='utf-8')
    montage=np.vstack([np.hstack(tiles[i:i+3]) for i in (0,3,6)])
    (out/'nine_stages.jpg').write_bytes(cv2.imencode('.jpg',montage,[cv2.IMWRITE_JPEG_QUALITY,92])[1].tobytes())
    Path(result['photos'],'nine_stages.jpg').write_bytes((out/'nine_stages.jpg').read_bytes())
    print(json.dumps({k:metrics[k] for k in ('state','engineering_checks','geometry','photometry')},ensure_ascii=False,indent=2))

if __name__=='__main__':analyze(Path(sys.argv[1]))
