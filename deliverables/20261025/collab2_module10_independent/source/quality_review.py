"""Independent supplementary review; measured quantities never imply acceptance."""
from pathlib import Path
import argparse,hashlib,json,math
import cv2
import numpy as np

def require(test,message):
    if not test:raise ValueError(message)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def edge_scale(grid,row,col,square_mm=25.):
    """Local image Jacobian in the normal direction of a vertical grid edge."""
    g=np.asarray(grid,dtype=np.float64).reshape(8,11,2)
    require(np.isfinite(g).all() and square_mm>0,'Invalid grid/scale')
    require(0<=row<7 and 0<col<10,'Need both neighbors and two edge endpoints')
    tangent=g[row+1,col]-g[row,col];length=float(np.linalg.norm(tangent))
    require(length>1e-6,'Degenerate edge')
    normal=np.array([-tangent[1],tangent[0]])/length
    mid=(g[row]+g[row+1])*.5
    cross=(mid[col+1]-mid[col-1])/(2*square_mm)
    scale=abs(float(cross@normal))
    require(math.isfinite(scale) and scale>1e-6,'Degenerate normal scale')
    angle=math.degrees(math.atan2(abs(tangent[0]),abs(tangent[1])))
    return dict(normal_px_per_mm=scale,slant_deg_from_vertical=angle,
        tangent_px_per_mm=length/square_mm,
        method='Central-difference local planar Jacobian, approximate; not traceable absolute metrology')

def convert_mtf(cy_per_px,px_per_mm):
    require(math.isfinite(cy_per_px) and 0<cy_per_px<=.5,'MTF outside image Nyquist')
    require(math.isfinite(px_per_mm) and px_per_mm>0,'Bad physical scale')
    return cy_per_px*px_per_mm

def eligibility(conditions):
    required=('exposure_readback_verified','white_balance_readback_verified','same_physical_edge',
        'bitstream_parameter_provenance','optics_epoch_confirmed','static_scene_confirmed',
        'slant_within_selected_method_domain','matched_radiometric_pipeline','scale_recorded')
    missing=[k for k in required if conditions.get(k) is not True]
    return dict(status='ELIGIBLE_FOR_REVIEW' if not missing else 'NOT_COMPARABLE',missing=missing,
        quality_acceptance='NOT_EVALUATED',note='Eligibility does not establish numerical quality pass')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--capture',required=True,type=Path)
    ap.add_argument('--mtf-report',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    a=ap.parse_args();require(not a.out.exists(),'Use a new output directory')
    c=json.loads((a.capture/'capture_session.json').read_text(encoding='utf-8'))
    m=json.loads((a.mtf_report/'results.json').read_text(encoding='utf-8'))
    require(not c['errors'] and len(c['frames'])==9,'Incomplete real capture')
    frames={f['path']:f for f in c['frames']}
    for name,f in frames.items():
        require(sha(a.capture/name)==f['sha256'],'Changed source SHA: '+name)
        require(f['corners_found'] and len(f['corners_xy'])==88,'Need complete 88 corners')
    rows=[]
    for item in m['measurements']:
        # Frozen E8 reports retain metrics with four decimal places in CLI stdout.
        if item['metric']!='mtf50':continue
        frame=next(f for f in m['frames'] if f['id']==item['frame_id'])
        filename=frame['source']['path'];f=frames[filename]
        metric=item.get('measurement',{}).get('curve_crossing')
        require(metric is not None,'Unknown frozen measurement structure')
        col={'center_edge':5,'outer_edge':1}[item['roi_id']]
        scale=edge_scale(f['corners_xy'],3,col)
        rows.append(dict(frame_id=item['frame_id'],source=filename,source_sha256=f['sha256'],
            role=frame['role'],roi_id=item['roi_id'],mtf50_cy_per_px=float(metric),
            mtf50_cy_per_mm_approx=convert_mtf(float(metric),scale['normal_px_per_mm']),**scale))
    require(len(rows)==12,'Expected 12 frozen single-side E8 metrics')
    all_angles=[r['slant_deg_from_vertical'] for r in rows]
    checks=dict(exposure_readback_verified=False,white_balance_readback_verified=False,
        same_physical_edge=True,bitstream_parameter_provenance=True,optics_epoch_confirmed=True,
        static_scene_confirmed=True,slant_within_selected_method_domain=all(5<=v<=15 for v in all_angles),
        matched_radiometric_pipeline=False,scale_recorded=True)
    result=dict(schema=1,evidence_kind='REANALYSIS_OF_EXISTING_REAL_CAPTURE',new_capture=False,
        capture_session_sha256=sha(a.capture/'capture_session.json'),mtf_report_sha256=sha(a.mtf_report/'results.json'),
        bitstream_sha256=c['bitstream_sha256'],optics_epoch='Human confirmed calibration and all captures AFTER lens replacement',
        exposure=c['conditions']['exposure'],white_balance=c['conditions']['white_balance'],
        source_transport=c['capture_transport'],frames_verified=len(frames),measurements=rows,
        selected_slant_domain=dict(deg=[5,15],authority='Existing E8 tool operational recommendation, NOT official contest threshold'),
        eligibility=eligibility(checks),checks=checks,
        limitations=['Cycles/mm uses a local image Jacobian from nominal 25mm squares; print accuracy/flatness not independently measured.',
            'No retroactive exposure or WB lock; values stay UNKNOWN, no fabricated register readback.',
            'Card MJPG transport and interpolation affect SFR; PNG only preserves decoded pixels.',
            'Existing E8 side metrics retained; no new official acceptance threshold.',
            'No new current-camera images are claimed; historical batch stays immutable.'])
    a.out.mkdir(parents=True)
    (a.out/'review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    lines=['# 真实素材尺度归一化补充分析','',
        '12项单侧指标转换为局部图卡平面近似cycles/mm；不据此签收画质。',
        '镜头时间关系以用户最新确认为准：标定及采集均在更换镜头后。',
        '','| 原帧 | 位置 | cy/px | 法向px/mm | 近似cy/mm | 斜角° |','|---|---|---:|---:|---:|---:|']
    for r in rows:lines.append(f"| {r['source']} | {r['roi_id']} | {r['mtf50_cy_per_px']:.4f} | {r['normal_px_per_mm']:.4f} | {r['mtf50_cy_per_mm_approx']:.4f} | {r['slant_deg_from_vertical']:.3f} |")
    lines+=['','可比性：'+result['eligibility']['status'],'未满足：'+', '.join(result['eligibility']['missing']),
        '','仍需受控光照/读回曝光白平衡及合适倾角的新素材；现有4fps校正输出可用于静态采集，不代表30fps处理通过。']
    (a.out/'review.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(frames=9,measurements=len(rows),eligibility=result['eligibility']),ensure_ascii=False))

if __name__=='__main__':main()
