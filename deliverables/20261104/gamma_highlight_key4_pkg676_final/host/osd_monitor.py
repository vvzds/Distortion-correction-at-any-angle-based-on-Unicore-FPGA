"""Send calibration values to the existing FPGA HDMI OSD."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

import cv2

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from analyze_board_checker import detect
from check_real_images import straightness,sfr
from model import affine,load_calibration
from protocol import Connection


def calibration_rows(c):
    """Build the four calibration-only rows shown by the KEY4 HDMI overlay."""
    return {
        0:f"FX={c['fx']:.4f} FY={c['fy']:.4f}",
        1:f"CX={c['cx']:.4f} CY={c['cy']:.4f}",
        2:f"K1={c['k1']:+.6f} K2={c['k2']:+.6f}",
        3:f"P1={c['p1']:+.6f} P2={c['p2']:+.6f}",
    }


def status_line(status,fps):
    if status['core_fault'] or status['write_fault']:
        return f"FPGA FAULT! SEQ={status['active_sequence']}"
    rate='--.--' if fps is None else f'{fps:05.2f}'
    return (f"PUB={rate} FPS INV={status['invalid_pixels']} "
            f"SEQ={status['active_sequence']}")[:48]


def open_capture(index):
    backend=cv2.CAP_DSHOW if sys.platform=='win32' else cv2.CAP_ANY
    if index is None:
        try:
            from cv2_enumerate_cameras import enumerate_cameras
        except ImportError as error:
            raise RuntimeError('Install cv2-enumerate-cameras or pass --camera-index') from error
        matches=[c for c in enumerate_cameras(backend)
                 if c.name=='Hagibis' and 'vid_345f' in c.path.lower()]
        if len(matches)!=1:raise RuntimeError(f'Expected one Hagibis capture card, found {len(matches)}')
        index=matches[0].index
    cap=cv2.VideoCapture(index,backend)
    if not cap.isOpened():raise RuntimeError(f'Cannot open capture index {index}; close OBS first')
    cap.set(cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT,1080)
    cap.set(cv2.CAP_PROP_FPS,30)
    return cap,index


def assess_frame(image):
    corners=detect(image)
    straight=straightness(corners)
    edge=sfr(image,corners)
    return {'straightness':straight,
            'mtf50_cycles_per_pixel':edge['median_mtf50_cycles_per_pixel'],
            'accepted_sfr_edges':edge['accepted_edges'],
            'method':'11x8 checker TLS straightness; slanted checker-edge comparative SFR, not ISO12233 certified'}


def measure(link,camera_index,output):
    cap,index=open_capture(camera_index)
    samples=[]
    try:
        link.osd_enable(False)
        # Capture-card buffering and the FPGA display boundary can lag the UART command.
        for _ in range(15):
            if not cap.grab():raise RuntimeError('Capture card frame read failed')
        for _ in range(3):
            for _ in range(5):
                if not cap.grab():raise RuntimeError('Capture card frame read failed')
            ok,frame=cap.read()
            if not ok or frame.shape[:2]!=(1080,1920):
                raise RuntimeError('Expected 1920x1080 decoded capture')
            samples.append(frame)
    finally:
        link.osd_enable(True)
        cap.release()
    output.mkdir(parents=True,exist_ok=False)
    report={'captured_at':datetime.now().astimezone().isoformat(),
            'capture_device_index':index,'input':'FPGA HDMI through capture card, OSD disabled during capture',
            'frames':[]}
    for i,image in enumerate(samples):
        path=output/f'raw_frame_{i}.png'
        encoded,png=cv2.imencode('.png',image)
        if not encoded:raise RuntimeError('Could not encode capture frame')
        path.write_bytes(png.tobytes())
        item={'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        try:item.update(assess_frame(image))
        except ValueError as error:item['error']=str(error)
        report['frames'].append(item)
    valid=[x for x in report['frames'] if 'straightness' in x]
    if valid:
        report['median_grid_rms_px']=statistics.median(x['straightness']['rms_px'] for x in valid)
        edge_values=[x['mtf50_cycles_per_pixel'] for x in valid if x['mtf50_cycles_per_pixel'] is not None]
        report['median_mtf50_cycles_per_pixel']=statistics.median(edge_values) if edge_values else None
        report['accepted_sfr_edges']=sum(x['accepted_sfr_edges'] for x in valid)
    else:
        report['median_grid_rms_px']=None
        report['median_mtf50_cycles_per_pixel']=None
        report['accepted_sfr_edges']=0
    (output/'measurement.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',required=True,help='FPGA control UART, not the JY901P COM port')
    p.add_argument('--calibration',type=Path,default=ROOT/'calibration/ov5640_1080p.json')
    p.add_argument('--camera-index',type=int,help='Hagibis DirectShow index; auto-detected if helper installed')
    p.add_argument('--measure-once',action='store_true',help='Capture three clean checker frames then report')
    p.add_argument('--duration',type=float,default=0,help='Seconds; zero keeps status running until Ctrl+C')
    a=p.parse_args()
    if a.duration<0:raise ValueError('Duration must be nonnegative')
    c=load_calibration(a.calibration)
    link=Connection(a.port)
    try:
        link.osd_update(calibration_rows(c))
        print('OSD enabled on FPGA HDMI. Calibration values are from the host file, not FPGA readback.',flush=True)
        if a.measure_once:
            folder=ROOT/'reports/osd_measurements'/datetime.now().strftime('%Y%m%d_%H%M%S')
            print(json.dumps(measure(link,a.camera_index,folder),ensure_ascii=False,indent=2),flush=True)
        started=time.monotonic();previous=None
        while a.duration==0 or time.monotonic()-started<a.duration:
            status=link.status();now=time.monotonic()
            fps=None
            if previous:
                delta=(status['frames']-previous[1])&0xffffffff
                fps=delta/(now-previous[0])
            previous=(now,status['frames'])
            print(status_line(status,fps),flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        link.close()


if __name__=='__main__':main()
