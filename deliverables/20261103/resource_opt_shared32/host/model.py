"""Brown4 output-to-input map, affine command compilation and tile preflight.

Coordinates are screen coordinates (origin top left). DDR row inversion belongs
exclusively to the hardware address adapter. Affine A maps destination pixels to
the ideal, undistorted source plane; Brown4 then maps to distorted source pixels.
"""
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def load_calibration(path=ROOT / 'calibration/ov5640_1080p.json'):
    c = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if c.get('model') != 'brown4' or (c['width'], c['height']) != (1920, 1080):
        raise ValueError('Expected Brown4 calibration for 1920x1080')
    if not all(np.isfinite(c[k]) for k in ('fx','fy','cx','cy','k1','k2','p1','p2')):
        raise ValueError('Non-finite calibration')
    if not (128 <= c['fx'] <= 8191 and 128 <= c['fy'] <= 8191):
        raise ValueError('Focal length outside supported range')
    if not (0<=c['cx']<=1919 and 0<=c['cy']<=1079):
        raise ValueError('Principal point must lie inside the 1920x1080 image')
    if any(abs(c[k])>=2 for k in ('k1','k2','p1','p2')):
        raise ValueError('Brown coefficient magnitude must be < 2')
    return c

def affine(angle=0., zoom=1., tx=0., ty=0., shear=0.):
    """Positive angle rotates the displayed image clockwise (screen y down)."""
    if not (0.5 <= zoom <= 8.):
        raise ValueError('Zoom must be in [0.5, 8]')
    theta = np.deg2rad(angle)
    forward = zoom * np.array([[np.cos(theta), -np.sin(theta)],
                               [np.sin(theta), np.cos(theta)]])
    forward = forward @ np.array([[1., shear], [0., 1.]])
    inv = np.linalg.inv(forward)
    center = np.array([959.5, 539.5])
    offset = center - inv @ (center + [tx, ty])
    return np.column_stack([inv, offset])

def compile_registers(c, a=None, adaptive=True, feedback_tag=None, smooth=False,
                      projective=None):
    a = affine() if a is None else np.asarray(a, dtype=float)
    if a.shape != (2,3) or not np.all(np.isfinite(a)):
        raise ValueError('Affine must be a finite 2x3 inverse matrix')
    values = [a[0,0]/c['fx'], a[0,1]/c['fx'], (a[0,2]-c['cx'])/c['fx'],
              a[1,0]/c['fy'], a[1,1]/c['fy'], (a[1,2]-c['cy'])/c['fy'],
              c['fx'],c['fy'],c['cx'],c['cy'],c['k1'],c['k2'],c['p1'],c['p2'],
              int(adaptive),(0 if feedback_tag is None else 65536 | (int(feedback_tag)&65535)) | (int(smooth)<<17)]
    scales = [28,28,20,28,28,20,16,16,16,16,22,22,22,22,0,0]
    regs = [int(round(v*(1<<q))) for v,q in zip(values,scales)]
    if projective is not None:
        g0,g1=(float(projective[0]),float(projective[1]))
        if not np.isfinite([g0,g1]).all():
            raise ValueError('Projective coefficients must be finite')
        qg0,qg1=int(round(g0*(1<<14))),int(round(g1*(1<<14)))
        if any(not -32768<=q<32768 for q in (qg0,qg1)):
            raise ValueError('Projective Q14 coefficient outside signed 16-bit range')
        tag=0 if feedback_tag is None else int(feedback_tag)&65535
        regs[14]=((qg0&65535)<<16)|int(adaptive)|(int(smooth)<<1)|(
            int(feedback_tag is not None)<<2)|8
        regs[15]=((qg1&65535)<<16)|tag
        regs=[n if n<2**31 else n-2**32 for n in regs]
    if any(not -(1<<31) <= n < (1<<31) for n in regs):
        raise ValueError('Parameter encoding overflow')
    if any(abs(regs[i]) >= (1<<23) for i in (10,11,12,13)):
        raise ValueError('Brown coefficient magnitude must be < 2')
    return regs

def float_map(c, a=None, projective=None):
    a = affine() if a is None else np.asarray(a)
    v,u = np.mgrid[:c['height'], :c['width']].astype(np.float64)
    x = (a[0,0]*u+a[0,1]*v+a[0,2]-c['cx'])/c['fx']
    y = (a[1,0]*u+a[1,1]*v+a[1,2]-c['cy'])/c['fy']
    if projective is not None:
        g0,g1=projective
        denominator=1+g0*x+g1*y
        projective_ok=(denominator>=.5)&(denominator<=1.5)
        safe_denominator=np.where(projective_ok,denominator,1.)
        x,y=x/safe_denominator,y/safe_denominator
    else:
        projective_ok=True
    r2 = x*x+y*y
    radial = 1+c['k1']*r2+c['k2']*r2*r2
    sx = c['fx']*(x*radial+2*c['p1']*x*y+c['p2']*(r2+2*x*x))+c['cx']
    sy = c['fy']*(y*radial+c['p1']*(r2+2*y*y)+2*c['p2']*x*y)+c['cy']
    valid = projective_ok&(np.abs(x)<=1.5)&(np.abs(y)<=1.5)&(sx>=0)&(sx<=1919)&(sy>=0)&(sy<=1079)
    return sx,sy,valid

def fixed_map(regs, u=None, v=None):
    """Integer golden model, matching truncation after each RTL pipeline stage."""
    if u is None:
        v,u = np.mgrid[:1080,:1920].astype(np.int64)
    u,v = np.asarray(u,dtype=np.int64),np.asarray(v,dtype=np.int64)
    n11,n12,n13,n21,n22,n23,fx,fy,cx,cy,k1,k2,p1,p2,_,_ = regs
    x = ((n11*u+n12*v)>>8)+n13
    y = ((n21*u+n22*v)>>8)+n23
    norm_ok = (np.abs(x)<=1572864)&(np.abs(y)<=1572864)
    if int(regs[14]) & 8:
        def q14(word):
            raw=(int(word)&0xffffffff)>>16
            return raw-(65536 if raw&0x8000 else 0)
        g0,g1=q14(regs[14]),q14(regs[15])
        denominator=(1<<20)+((g0*x+g1*y)>>14)
        projective_ok=(denominator>=1<<19)&(denominator<=3<<19)
        norm_ok &= projective_ok
        safe_denominator=np.where(projective_ok,denominator,1<<20)
        reciprocal_seed=np.array([1973790,1766023,1597830,1458888,1342177,
            1242757,1157049,1082401,1016801,958698,906877,860370,818401,
            780336,745654,713924],dtype=np.int64)
        index=np.minimum((safe_denominator-(1<<19))>>16,15)
        reciprocal=reciprocal_seed[index]
        reciprocal=(reciprocal*((2<<20)-((safe_denominator*reciprocal)>>20)))>>20
        reciprocal=(reciprocal*((2<<20)-((safe_denominator*reciprocal)>>20)))>>20
        x=(x*reciprocal)>>20
        y=(y*reciprocal)>>20
        norm_ok &= (np.abs(x)<=1572864)&(np.abs(y)<=1572864)
    # Invalid normalized points are neutralized before the polynomial so that
    # adversarial transforms cannot overflow downstream fixed-point operators.
    x,y = np.where(norm_ok,x,0),np.where(norm_ok,y,0)
    xx,yy,xy = (x*x)>>20,(y*y)>>20,(x*y)>>20
    r2 = xx+yy
    t = ((k2*r2)>>22)+(k1>>2)
    radial = (1<<20)+((t*r2)>>20)
    xd = ((x*radial)>>20)+(((p1*xy)>>22)<<1)+((p2*(r2+2*xx))>>22)
    yd = ((y*radial)>>20)+(((p2*xy)>>22)<<1)+((p1*(r2+2*yy))>>22)
    sx,sy = ((fx*xd)>>20)+cx,((fy*yd)>>20)+cy
    valid = norm_ok&(sx>=0)&(sx<=1919*65536)&(sy>=0)&(sy<=1079*65536)
    return sx,sy,valid

def tile_profile(sx,sy,valid):
    """Every valid pixel contributes to bounds; no corner-only approximation."""
    rows=[]
    for y in range(0,1080,32):
        for x in range(0,1920,64):
            sl=np.s_[y:min(y+32,1080),x:x+64]
            mask=valid[sl]
            if not np.any(mask):
                rows.append((0,0,0));continue
            px,py=sx[sl][mask]>>16,sy[sl][mask]>>16
            xmin=int(px.min())&~15; ymin=int(py.min())&~1
            xmax=min(int(px.max())+1,1919); ymax=min(int(py.max())+1,1079)
            beats=(xmax//16-xmin//16+1);height=ymax-ymin+1
            if beats>16 or height>256:
                raise ValueError(f'Tile ({x},{y}) requires {beats*16}x{height}; max 256x256')
            rows.append((beats,height,beats*height))
    z=np.asarray(rows)
    return {'tiles':len(rows),'max_patch_width':int(z[:,0].max()*16),
            'max_patch_height':int(z[:,1].max()),'read_beats':int(z[:,2].sum()),
            'read_bytes_per_frame':int(z[:,2].sum()*32),
            'row_commands':int(z[:,1].sum())}

def preflight(c,a=None,adaptive=True,projective=None):
    regs=compile_registers(c,a,adaptive,projective=projective)
    sx,sy,ok=fixed_map(regs)
    report=tile_profile(sx,sy,ok)
    report['valid_fraction']=float(ok.mean())
    return regs,report
