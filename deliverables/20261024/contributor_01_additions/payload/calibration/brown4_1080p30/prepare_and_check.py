"""Offline only: frozen UART encoding, independent Brown4 reference, RTL vectors."""
import csv
import hashlib
import importlib.util
import json
import re
import struct
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT = 1920, 1080
VALUES = dict(zip(('fx','fy','cx','cy','k1','k2','p1','p2'), (
    '1507.710442199695','1507.403518870939','883.533081692948',
    '568.687748120301','-0.381482584692','0.156698401312',
    '-0.000303016236','-0.000110983241')))
Q = {k: int((Decimal(v)*65536).to_integral_value(rounding=ROUND_HALF_EVEN))
     for k,v in VALUES.items()}

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()

def verify_manifest(root,base=None):
    base=root if base is None else base
    rows = list(csv.DictReader((root/'MANIFEST_SHA256.tsv').open(encoding='utf-8-sig'), delimiter='\t'))
    for r in rows:
        p = base/r['path']
        assert p.stat().st_size == int(r['bytes']), p
        assert digest(p) == r['sha256'].upper(), p
    return len(rows)

def float_map(parameters):
    """Inverse resampling: corrected destination -> distorted source, same K."""
    fx,fy,cx,cy,k1,k2,p1,p2 = [parameters[k] for k in VALUES]
    yy,xx = np.indices((HEIGHT,WIDTH), dtype=np.float64)
    x=(xx-cx)/fx; y=(yy-cy)/fy
    r2=x*x+y*y
    rad=1+k1*r2+k2*r2*r2
    sx=fx*(x*rad+2*p1*x*y+p2*(r2+2*x*x))+cx
    sy=fy*(y*rad+p1*(r2+2*y*y)+2*p2*x*y)+cy
    return np.clip(sx,0,WIDTH-1), np.clip(sy,0,HEIGHT-1)

def fixed_map(q):
    """G4 arithmetic model; independently checked against actual map RTL."""
    yy,xx=np.indices((HEIGHT,WIDTH), dtype=np.int64)
    # This calibration stays below signed-64 product limits, checked below.
    invx=(1<<52)//q['fx']; invy=(1<<52)//q['fy']
    x=(((xx<<16)-q['cx'])*invx)>>28
    y=(((yy<<16)-q['cy'])*invy)>>28
    xs=x*x; ys=y*y; xy=(x*y)>>24
    r2=(xs+ys)>>24; xs=xs>>24; ys=ys>>24
    assert int(r2.max())**2 < 2**63
    r4=(r2*r2)>>24
    rad=(1<<24)+((q['k1']*r2)>>16)+((q['k2']*r4)>>16)
    xd=((x*rad)>>24)+(((q['p1']*xy)>>16)<<1)+((q['p2']*(r2+2*xs))>>16)
    yd=((y*rad)>>24)+(((q['p2']*xy)>>16)<<1)+((q['p1']*(r2+2*ys))>>16)
    assert max(int(np.abs(xd).max())*q['fx'],int(np.abs(yd).max())*q['fy']) < 2**63
    sx=((xd*q['fx'])>>24)+q['cx']; sy=((yd*q['fy'])>>24)+q['cy']
    return np.clip(sx,0,(WIDTH-1)<<16),np.clip(sy,0,(HEIGHT-1)<<16)

def pattern(x,y,kind):
    if kind==0:
        r=((x//64)+(y//128))&31; g=((x//40)+(y//80))&63; b=((x//80)+(y//64))&31
    else:
        r=(x*13+y*7)&31;g=(x*29+y*11)&63;b=(x*3+y*23)&31
    return (r<<11)|(g<<5)|b

def interpolate(sx,sy,kind,fixed=False):
    if fixed:
        x=sx>>16;y=sy>>16;wx=(sx&65535)>>4;wy=(sy&65535)>>4;scale=4096
    else:
        x=np.floor(sx).astype(np.int64);y=np.floor(sy).astype(np.int64)
        wx=sx-x;wy=sy-y;scale=1
    x1=np.minimum(x+1,WIDTH-1);y1=np.minimum(y+1,HEIGHT-1)
    p=[pattern(x,y,kind),pattern(x1,y,kind),pattern(x,y1,kind),pattern(x1,y1,kind)]
    out=np.zeros_like(x)
    for shift,mask in ((11,31),(5,63),(0,31)):
        a,b,c,d=[(v>>shift)&mask for v in p]
        s=((a*(scale-wx)+b*wx)*(scale-wy)+(c*(scale-wx)+d*wx)*wy)
        channel=(s+(1<<23))>>24 if fixed else np.floor(s+0.5).astype(np.int64)
        assert channel.min()>=0 and channel.max()<=mask
        out|=channel<<shift
    return out.astype(np.uint16)

def coord_stats(ax,ay,bx,by):
    dx=np.abs(ax-bx);dy=np.abs(ay-by);d=np.hypot(dx,dy)
    return dict(max_abs_x_px=float(dx.max()),max_abs_y_px=float(dy.max()),
                max_euclidean_px=float(d.max()),rms_euclidean_px=float(np.sqrt(np.mean(d*d))),
                p95_euclidean_px=float(np.percentile(d,95)))

def channel_stats(a,b):
    errs=np.maximum.reduce([np.abs(((a.astype(np.int32)>>s)&m)-((b.astype(np.int32)>>s)&m))
                            for s,m in ((11,31),(5,63),(0,31))])
    return dict(max_channel_lsb=int(errs.max()),within_one_fraction=float(np.mean(errs<=1)),
                over_two_pixels=int(np.sum(errs>2)))

def write_hex(p,array,width):
    with p.open('w',encoding='ascii',newline='\n') as f:
        for value in array.flat: f.write(f'{int(value):0{width}x}\n')

def write_source_words(kind):
    """Low 16 bits are even x / first pixel, row order is DDR y_mem."""
    yy,xx=np.indices((HEIGHT,WIDTH),dtype=np.int64)
    pixels=pattern(xx,yy,kind)[::-1].reshape(-1,16)
    with (ROOT/f'vectors/source_words_{kind}.hex').open('w',encoding='ascii',newline='\n') as f:
        for group in pixels:
            f.write(''.join(f'{int(value):04x}' for value in group[::-1])+'\n')

def main():
    for name in ('parameters','vectors','reports','sim','logs'): (ROOT/name).mkdir(exist_ok=True)
    g4_count=verify_manifest(ROOT/'received/G4')
    integration=ROOT/'received/integration/integ_ws_regression_pkg_20261019'
    integration_count=verify_manifest(integration,integration.parent)
    calibration_note=(ROOT/'received/标定结果说明(1).md').read_text(encoding='utf-8-sig')
    for key,value in VALUES.items():
        found=re.search(r'^'+key+r'\s*=\s*([-\d.]+)',calibration_note,re.M)
        assert found and Decimal(found.group(1))==Decimal(value),key
    for name in ('undistort_map.v','undistort_core.v','undistort_bilinear.v','undistort_line_cache.v'):
        assert digest(ROOT/'received/G4/source/rtl'/name)==digest(integration/'source/rtl'/name),name
    tool=ROOT/'reference_uart/uart_tool.py'
    spec=importlib.util.spec_from_file_location('frozen_uart_tool',tool)
    uart=importlib.util.module_from_spec(spec);spec.loader.exec_module(uart)
    floats={k:float(v) for k,v in VALUES.items()};quant={k:v/65536 for k,v in Q.items()}
    uart.validate_parameters(floats);uart.validate_parameters(quant)
    payload=b''.join(struct.pack('<i',Q[k]) for k in VALUES)
    wire=bytes.fromhex('AA 55 01 20')+payload+bytes([sum(payload)&255])
    assert uart.build_distortion(floats)==wire
    assert uart.parse_frame(wire)==(1,32,payload)
    identity={k:(0 if k in ('k1','k2','p1','p2') else floats[k]) for k in VALUES}
    rows=[]
    for k in VALUES:
        assert struct.unpack('<i',struct.pack('<I',Q[k]&0xffffffff))[0]==Q[k]
        assert (Q[k]<0)==(floats[k]<0)
        rows.append(dict(name=k,input=VALUES[k],signed_integer=Q[k],hex=f'{Q[k]&0xffffffff:08X}',
                         little_endian=struct.pack('<i',Q[k]).hex(' ').upper(),
                         decoded=quant[k],quantization_error=quant[k]-floats[k],
                         g02_range=uart.LIMITS[k],range_pass=True))
    for label,p in [('real',floats),('identity',identity)]:
        frame=uart.build_distortion(p)
        (ROOT/f'parameters/{label}_0x01.bin').write_bytes(frame)
        (ROOT/f'parameters/{label}_0x01.hex').write_text(frame.hex(' ').upper()+'\n',encoding='ascii')
        write_hex(ROOT/f'vectors/{label}_uart_bytes.hex',np.frombuffer(frame,dtype=np.uint8),2)
    affine={'a11':1,'a12':0,'a21':0,'a22':1,'tx':0,'ty':0}
    (ROOT/'parameters/affine_disabled_0x02.bin').write_bytes(uart.build_affine(affine,0))
    (ROOT/'parameters/gamma_disabled_0x04.bin').write_bytes(uart.frame(4,bytes(4)))
    for label,p in [('real',floats),('identity',identity)]:
        with (ROOT/f'parameters/{label}_parameters.csv').open('w',newline='',encoding='ascii') as f:
            writer=csv.DictWriter(f,fieldnames=uart.CSV_HEADER);writer.writeheader()
            writer.writerow(dict(p,**affine,aff_en=0,gamma_en=0))
    vh='// Generated Q16.16 constants; not automatic FPGA initialization.\n'
    for k in VALUES: vh+=f'localparam signed [31:0] CAL_{k.upper()} = 32\'sh{Q[k]&0xffffffff:08X};\n'
    (ROOT/'parameters/calibration_q16.vh').write_text(vh,encoding='ascii')
    (ROOT/'parameters/parameter_encoding.json').write_text(json.dumps(dict(
        image=[WIDTH,HEIGHT],fps=30,model='Brown4, k3=0, K_out=K_in',
        origin='top-left; x right; y down',order=list(VALUES),parameters=rows,
        cmd01_frame_bytes=len(wire),cmd01_checksum=f'{wire[-1]:02X}',
        cmd01_hex=wire.hex(' ').upper(),g4_manifest_verified=g4_count,
        integration_manifest_verified=integration_count,
        calibration_source_sha256=digest(ROOT/'received/标定结果说明(1).md')),
        indent=2),encoding='utf-8')
    original=float_map(floats);qfloat=float_map(quant);fixed=fixed_map(Q)
    metrics=dict(pixels=WIDTH*HEIGHT,
        quantized_vs_original=coord_stats(*qfloat,*original),
        arithmetic_vs_quantized=coord_stats(fixed[0]/65536,fixed[1]/65536,*qfloat),
        total_vs_original=coord_stats(fixed[0]/65536,fixed[1]/65536,*original))
    assert metrics['arithmetic_vs_quantized']['max_abs_x_px']<=0.02
    assert metrics['arithmetic_vs_quantized']['max_abs_y_px']<=0.02
    assert metrics['total_vs_original']['max_abs_x_px']<=0.02
    assert metrics['total_vs_original']['max_abs_y_px']<=0.02
    # Storage/output order is memory row ascending, display row descending.
    packed=(fixed[0]<<27)|fixed[1]
    write_hex(ROOT/'vectors/map_expected.hex',packed[::-1],14)
    np.savez_compressed(ROOT/'vectors/reference_maps.npz',original_x=original[0],original_y=original[1],
                        quantized_x=qfloat[0],quantized_y=qfloat[1],fixed_x=fixed[0],fixed_y=fixed[1])
    yy,xx=np.indices((HEIGHT,WIDTH),dtype=np.int64)
    write_hex(ROOT/'vectors/identity_pixels.hex',pattern(xx,yy,1)[::-1],4)
    for kind in (0,1):
        write_source_words(kind)
        result=interpolate(*fixed,kind,True)
        float_result=interpolate(*qfloat,kind)
        full_float_result=interpolate(*original,kind)
        metrics[f'pattern_{kind}_vs_quantized_float']=channel_stats(result,float_result)
        metrics[f'pattern_{kind}_vs_original_float']=channel_stats(result,full_float_result)
        for name in (f'pattern_{kind}_vs_quantized_float',f'pattern_{kind}_vs_original_float'):
            assert metrics[name]['max_channel_lsb']<=2
            assert metrics[name]['within_one_fraction']>=0.995
        write_hex(ROOT/f'vectors/real_pixels_{kind}.hex',result[::-1],4)
    # Screen->memory conversion for both interpolation rows, every output pixel.
    i=fixed[0]>>16;j=fixed[1]>>16
    a=1079-j;b=np.maximum(a-1,0)
    assert a.min()>=0 and a.max()<=1079 and b.min()>=0 and b.max()<=1079
    for slot in range(4):
        for row in (a,b):
            address=(slot<<20)+row*960+(i>>1)
            assert address.min()>=(slot<<20)
            assert address.max()<(slot<<20)+1036800
            assert address.max()<1<<23
    metrics['all_pixels_source_address_check']='PASS (both rows, slots 0..3)'
    # Sequential corrected write addresses, both halfwords and all target slots.
    for slot in range(4,8):
        for x,y in ((0,0),(1919,0),(0,1079),(1919,1079)):
            ymem=1079-y
            word=(slot<<20)+ymem*960+(x>>1)
            assert word==(slot<<20)+((ymem*1920+x)//2)
            assert word<1<<23
    metrics['corrected_write_display_contract']='PASS: y_mem ascending, HDMI y_mem=1079-y_screen; x even low16'
    metrics['fixed_coordinate_range_px']=[float(fixed[0].min()/65536),float(fixed[0].max()/65536),
                                          float(fixed[1].min()/65536),float(fixed[1].max()/65536)]
    metrics['predicted_access']={}
    for label,fxmap,fymap in [('identity',xx<<16,yy<<16),('real',*fixed)]:
        rowa=1079-(fymap>>16);rowb=np.maximum(rowa-1,0)
        metrics['predicted_access'][label]=dict(max_source_row_span_per_output_line=int(
            np.max(np.max(rowa,axis=1)-np.min(rowb,axis=1)+1)))
    (ROOT/'reports/offline_metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    print(json.dumps(metrics,indent=2))
    print('UART 0x01:',wire.hex(' ').upper())

if __name__=='__main__':main()
