"""Offline fixed-crop coverage sweep using the calibrated production mapper.

This is sampled numerical evidence, not a proof for every camera pose or a
board test. Pixels absent from the source cannot be recovered by interpolation.
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'host'))
from model import affine, compile_registers, fixed_map, load_calibration
from stabilizer import fast_guard


def main():
    c = load_calibration()
    u = np.concatenate([np.arange(1920), np.arange(1920), np.zeros(1080), np.full(1080,1919)]).astype(np.int64)
    v = np.concatenate([np.zeros(1920), np.full(1920,1079), np.arange(1080), np.arange(1080)]).astype(np.int64)
    center = np.array([959.5,539.5])

    def margin(a, uu=u, vv=v):
        sx, sy, valid = fixed_map(compile_registers(c, a, False), uu, vv)
        return float(min(sx.min()/65536, 1919-sx.max()/65536,
                         sy.min()/65536, 1079-sy.max()/65536)), bool(valid.all())

    profiles=[]
    for zoom in [1.15, 1.4, 1.5, 1.6, 1.7, 1.8, 2., 2.1, 2.4]:
        values=[margin(affine(angle,zoom))[0] for angle in range(360)]
        symmetric=[]
        for angle in range(91):
            if not all(margin(affine(sign*angle,zoom))[1] for sign in [-1,1]):
                break
            symmetric.append(angle)
        profiles.append(dict(zoom=zoom,min_perimeter_margin_px=min(values),
                             worst_sample_angle=int(np.argmin(values)),
                             sampled_symmetric_roll_degrees=max(symmetric) if symmetric else None,
                             linear_field_fraction_vs_candidate01=1.15/zoom))
    worst=(float('inf'),None)
    cases=0
    # Sample all roll angles, translations at +/-90 ideal-source pixels and
    # stretch eigenvectors at several orientations. ShapeStabilizer bounds
    # each singular scale to [1/1.02,1.02] relative to the reference crop.
    for angle in range(0,360,5):
        for orientation in [0,45,90,135]:
            t=np.deg2rad(orientation)
            q=np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
            for scales in [(1.02,1.02),(1.02,1/1.02),(1/1.02,1.02)]:
                a=affine(angle,2.4)
                a[:,:2]=a[:,:2]@q@np.diag(scales)@q.T
                for dx,dy in [(-90,-90),(-90,90),(90,-90),(90,90)]:
                    a[:,2]=center+[dx,dy]-a[:,:2]@center
                    edge,valid=margin(a)
                    assert valid and edge>2,(angle,orientation,scales,dx,dy,edge)
                    if edge<worst[0]:
                        worst=(edge,dict(angle=angle,orientation=orientation,scales=scales,dx=dx,dy=dy,matrix=a.tolist()))
                    cases+=1
    # Full raster validation at sampled worst shape and four cardinal rolls.
    full=[]
    for label,a in [('sampled_worst',np.array(worst[1]['matrix']))]+[(str(angle),affine(angle,2.4)) for angle in [0,90,180,270]]:
        vv,uu=np.mgrid[:1080,:1920].astype(np.int64)
        edge,valid=margin(a,uu,vv)
        assert valid and edge>2
        guard=fast_guard(c,a)
        full.append(dict(case=label,valid_pixels=1920*1080,min_margin_px=edge,**guard))
    report=dict(passed=True,hardware_tested=False,fixed_zoom=2.4,
        launcher_zoom=1.5,launcher_reason='User found 2.4x crop excessive; 1.5x is a moderate trial, large-angle black corners accepted',
        baseline_zoom=1.15,linear_field_fraction_vs_candidate01=1.15/2.4,
        no_translation_profiles=profiles,envelope_samples=cases,
        sampled_min_perimeter_margin_px=worst[0],sampled_worst_case=worst[1],
        full_raster_checks=full,
        limits=['Sampled roll/shape/translation coverage, not proof of every continuous pose',
                'Translation envelope is +/-90 ideal-source pixels on each axis, not a guaranteed pitch angle',
                'Camera calibration uncertainty, fast motion, tracking loss and large translations remain',
                'No sensor mode change; output 1080p does not imply native detail after 2.4x enlargement'])
    (ROOT/'reports/fixed_crop_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
