"""Held-out real-image checks; no camera/serial connection or board claims.

SFR is a reproducible slanted-checker-edge estimate, not an ISO12233-certified
measurement. Frequency is cycles per output pixel; resize/crop changes scale.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import cv2,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'host'))
from model import load_calibration,compile_registers,fixed_map,float_map
from resample import bilinear565

def detect(image):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    ok,corners=cv2.findChessboardCornersSB(gray,(11,8),cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok:raise ValueError('Could not detect all 88 checker intersections')
    return corners.reshape(8,11,2).astype(float)

def straightness(corners):
    distances=[]
    for line in list(corners)+list(corners.transpose(1,0,2)):
        center=line.mean(axis=0);_,_,vh=np.linalg.svd(line-center,full_matrices=False)
        distances.extend(np.abs((line-center)@vh[1]).tolist())
    z=np.asarray(distances)
    return dict(rms_px=float(np.sqrt((z*z).mean())),p95_px=float(np.percentile(z,95)),max_px=float(z.max()))

def edge_sfr(gray,a,b):
    # Transpose near-horizontal edges so every scan line crosses a vertical edge.
    if abs(b[0]-a[0])>abs(b[1]-a[1]):gray=gray.T;a=a[::-1];b=b[::-1]
    if a[1]>b[1]:a,b=b,a
    slope=(b[0]-a[0])/(b[1]-a[1])
    angle=float(np.degrees(np.arctan(abs(slope))))
    if not 2<=angle<=20 or b[1]-a[1]<28:return None
    ys=np.arange(int(np.ceil(a[1]+.2*(b[1]-a[1]))),int(np.floor(b[1]-.2*(b[1]-a[1])))+1)
    if len(ys)<20:return None
    nominal=a[0]+slope*(ys-a[1]);xx=np.rint(nominal).astype(int)[:,None]+np.arange(-9,10)
    if xx.min()<0 or xx.max()>=gray.shape[1]:return None
    samples=gray[ys[:,None],xx].astype(float)
    contrast=np.mean(samples[:,-3:])-np.mean(samples[:,:3])
    if abs(contrast)<40:return None
    derivative=np.diff(samples,axis=1)*np.sign(contrast)
    weights=derivative.sum(axis=1)
    if np.any(weights<25):return None
    centroid=(derivative*(xx[:,:-1]+.5)).sum(axis=1)/weights
    fit=np.polyfit(ys,centroid,1)
    residual=centroid-np.polyval(fit,ys)
    if np.sqrt(np.mean(residual**2))>.7:return None
    distance=(xx-np.polyval(fit,ys)[:,None])/np.sqrt(1+fit[0]**2)
    bins=np.floor((distance+7)*4).astype(int);keep=(bins>=0)&(bins<56)
    count=np.bincount(bins[keep],minlength=56)
    if np.any(count==0):return None
    esf=np.bincount(bins[keep],weights=samples[keep],minlength=56)/count
    lsf=np.diff(esf)*np.sign(contrast)
    # Window the derivative, correct forward-difference response, FFT to SFR.
    window=np.hamming(len(lsf));spectrum=np.abs(np.fft.rfft(lsf*window,2048))
    if spectrum[0]<=0:return None
    f=np.fft.rfftfreq(2048,d=.25)
    spectrum=spectrum/spectrum[0]/np.maximum(np.sinc(f*.25),.1)
    crossing=np.flatnonzero((f>0)&(f<=.5)&(spectrum<=.5))
    if not len(crossing):return None
    i=int(crossing[0]);frequency=float(np.interp(.5,[spectrum[i],spectrum[i-1]],[f[i],f[i-1]]))
    return dict(mtf50_cycles_per_pixel=frequency,slant_degrees=angle,
                line_fit_rms_px=float(np.sqrt(np.mean(residual**2))),contrast=abs(float(contrast)),
                frequencies=f[f<=.5].tolist(),sfr=spectrum[f<=.5].tolist())

def sfr(image,corners):
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    results=[]
    for lines in [corners,corners.transpose(1,0,2)]:
        for line in lines:
            for a,b in zip(line[:-1],line[1:]):
                item=edge_sfr(gray,a,b)
                if item:results.append(item)
    if not results:return {'accepted_edges':0,'median_mtf50_cycles_per_pixel':None}
    values=[r['mtf50_cycles_per_pixel'] for r in results]
    frequencies=results[0]['frequencies']
    median_curve=np.median([r['sfr'] for r in results],axis=0).tolist()
    for r in results:r.pop('sfr');r.pop('frequencies')
    return dict(accepted_edges=len(results),median_mtf50_cycles_per_pixel=float(np.median(values)),
                p10_mtf50_cycles_per_pixel=float(np.percentile(values,10)),
                frequencies=frequencies,median_sfr=median_curve,edges=results)

def main():
    p=argparse.ArgumentParser();p.add_argument('--photos',default='D:/FPGA/photo/session_203513')
    a=p.parse_args();photos=Path(a.photos);out=ROOT/'reports/real_images';out.mkdir(parents=True,exist_ok=True)
    c=load_calibration();regs=compile_registers(c,adaptive=False)
    sx,sy,valid=fixed_map(regs);fx,fy,float_valid=float_map(c)
    session=json.loads((photos/'SESSION.json').read_text(encoding='utf-8-sig'))
    poses=[z for z in session['poses'] if z.get('dataset_role')=='held_out_validation']
    if len(poses)!=5:raise ValueError('Expected 5 held-out validation images in SESSION.json')
    report={'method':'Exact RGB565/Q0.8 bilinear bit model; same verified FPGA fixed map; gamma disabled',
            'hardware_tested':False,'sfr_method':'4x oversampled slanted checker edges, linear edge-centroid fit, Hamming LSF, forward-difference compensation; captured display values, no radiometric linearization; comparative estimate, not certified ISO12233',
            'straightness_method':'Total least squares line fit to every detected checker row and column; perpendicular residual in pixels; each corner contributes to both',
            'calibration':c,'images':[]}
    for pose in poses:
        path=photos/pose['path'];digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=pose['source_png_sha256']:raise ValueError('Source hash differs from capture manifest: '+str(path))
        image=cv2.imread(str(path));name=path.parent.name
        corrected=bilinear565(image,sx,sy,valid);reference=bilinear565(image,fx,fy,float_valid,fixed=False)
        common=valid&float_valid;difference=corrected.astype(float)-reference.astype(float)
        mse=float((difference[common]**2).mean())
        corners=[detect(z) for z in [image,corrected,reference]]
        item={'pose':name,'source_path':str(path),'source_sha256':digest,
              'original':straightness(corners[0]),'fixed_corrected':straightness(corners[1]),
              'float_reference':straightness(corners[2]),'fixed_vs_float_mae_8bit':float(np.abs(difference[common]).mean()),
              'fixed_vs_float_psnr_db':float(10*np.log10(255**2/mse)),
              'fixed_vs_float_p99_abs_8bit':float(np.percentile(np.abs(difference[common]),99)),
              'original_sfr':sfr(image,corners[0]),'corrected_sfr':sfr(corrected,corners[1]),
              'reference_sfr':sfr(reference,corners[2])}
        cv2.imwrite(str(out/f'{name}_corrected.png'),corrected)
        cv2.imwrite(str(out/f'{name}_reference.png'),reference)
        pair=np.hstack([image,corrected]);pair=cv2.resize(pair,(1440,405),interpolation=cv2.INTER_AREA)
        cv2.putText(pair,'Original',(20,30),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,220,255),2)
        cv2.putText(pair,'Fixed-point RGB565 corrected / gamma off',(740,30),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,220,255),2)
        cv2.imwrite(str(out/f'{name}_comparison.jpg'),pair)
        report['images'].append(item)
        print(name,'RMS:',item['original']['rms_px'],'->',item['fixed_corrected']['rms_px'],'PSNR',item['fixed_vs_float_psnr_db'],flush=True)
    (ROOT/'reports/real_image_quality.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('PASS held-out real-image checks; result describes offline processing only')

if __name__=='__main__':main()

