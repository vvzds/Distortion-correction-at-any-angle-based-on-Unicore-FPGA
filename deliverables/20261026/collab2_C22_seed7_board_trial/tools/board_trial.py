"""C22 seed7 SRAM board trial; immutable UART packets and timestamped evidence."""
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, json, sys, time

BASE = Path('C:/Users/叶翔/Documents/Codex/2026-10-10/x20/work')
sys.path.insert(0, str(BASE/'host_validation_deps'))
sys.path.insert(0, str(BASE/'affine_track_loop_review_20261020'))
REF = Path('C:/Users/叶翔/Documents/Codex/fpga-main/deliverables/20261025/collab2_module2_uart/source/reference')
ROOT = Path('C:/Users/叶翔/Desktop/yx/G7_C22_seed7真实板测_二号_20261026')
spec = importlib.util.spec_from_file_location('approved_uart', REF/'uart_tool_tlimfix.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=['baseline', 'affine'], default='baseline')
    args = ap.parse_args()
    out = ROOT/('02_'+args.phase+'_'+datetime.datetime.now().strftime('%H%M%S'))
    out.mkdir()
    log = dict(start=datetime.datetime.now().astimezone().isoformat(), phase=args.phase,
               bit_sha256='668d08ec6e19550ec5dcd86ebfad4ef0d595b6e66e912abb56e3d3bee8eaf145',
               wire=[], stages=[], errors=[])
    path = out/'board_trial.json'
    def save():
        path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
    class Wire:
        def __init__(self, connection): self.s = connection
        def __getattr__(self, name): return getattr(self.s, name)
        def write(self, data):
            n = self.s.write(data)
            log['wire'].append(dict(t=time.monotonic(), direction='TX', hex=data.hex(), written=n))
            save()
            if n != len(data): raise IOError('Partial UART write')
            return n
        def read(self, n=1):
            data = self.s.read(n)
            if data: log['wire'].append(dict(t=time.monotonic(), direction='RX', hex=data.hex()))
            return data
    from serial.tools import list_ports
    ports = [p for p in list_ports.comports() if (p.vid, p.pid)==(0x10c4, 0xea60)]
    if len(ports)!=1: raise RuntimeError('No unique CP2102')
    log['port'] = ports[0].device
    conn = tool.open_serial(ports[0].device)
    conn.timeout = .1
    c = Wire(conn)
    def query():
        c.write(tool.frame(5)); c.flush()
        start = time.monotonic()
        status = tool.read_status_frame(c)
        end = time.monotonic()
        if status & 255 != 0x12 or status & 0xfc00:
            raise ValueError('Unexpected status %08x' % status)
        return dict(t=(start+end)/2, query_start=start, query_end=end,
                    status='%08x'%status, pub_count=status>>16,
                    valid=bool(status&256), busy=bool(status&512))
    def send(data):
        tool.parse_frame(data); c.write(data); c.flush(); time.sleep(.05)
    identity_aff = dict(a11=1, a12=0, a21=0, a22=1, tx=0, ty=0)
    def capture(label):
        import cv2, numpy as np
        from camera_devices import enumerate_cameras
        cams = [cam for cam in enumerate_cameras() if cam.get('FriendlyName')=='Hagibis']
        if len(cams)!=1: raise RuntimeError('No unique Hagibis capture card')
        cap = cv2.VideoCapture(cams[0]['index'], cv2.CAP_DSHOW)
        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,1920); cap.set(cv2.CAP_PROP_FRAME_HEIGHT,1080)
            cap.set(cv2.CAP_PROP_FPS,30)
            start = time.monotonic(); count = 0; frame = None
            while count<60 and time.monotonic()-start<8:
                ok, image = cap.read()
                if ok: frame=image; count+=1
            if frame is None: raise RuntimeError('No capture frames')
            png = cv2.imencode('.png', frame)[1].tobytes()
            (out/(label+'.png')).write_bytes(png)
            cv2.imencode('.jpg',cv2.resize(frame,(960,540)))[1].tofile(str(out/(label+'_preview.jpg')))
            return dict(file=label+'.png',sha256=hashlib.sha256(png).hexdigest(),shape=list(frame.shape),
                        mean=float(np.mean(frame)),std=float(np.std(frame)),frames_read=count,
                        reported_capture_fps=cap.get(cv2.CAP_PROP_FPS),
                        note='Decoded HDMI capture; reported capture rate is not correction publication rate')
        finally: cap.release()
    def measure(label, seconds=10):
        stage = dict(label=label, samples=[])
        log['stages'].append(stage)
        start = time.monotonic()
        while True:
            row=query(); stage['samples'].append(row); save()
            if time.monotonic()-start>=seconds: break
            time.sleep(.5)
        first,last=stage['samples'][0],stage['samples'][-1]
        delta=(last['pub_count']-first['pub_count'])&65535
        if delta>=32768: raise ValueError('Counter reset/discontinuity')
        stage.update(delta=delta,elapsed=last['t']-first['t'],
                     publication_fps=delta/(last['t']-first['t']))
        stage['capture']=capture(label)
        save(); print(json.dumps({k:v for k,v in stage.items() if k!='samples'},ensure_ascii=False),flush=True)
    try:
        log['initial']=query(); save(); print('INITIAL',log['initial'],flush=True)
        if args.phase=='baseline':
            send(tool.build_mode(0)); send(tool.build_affine(identity_aff,enable=0))
            for label, name in [('identity','identity_0x01.bin'),('real','real_0x01.bin')]:
                data=(REF/'parameters'/name).read_bytes()
                if name=='real_0x01.bin' and hashlib.sha256(data).hexdigest()!='1ac17c4bea8947d1e4a84f50a7eaaf46c0b1d90dd4b8e8ba880bc01e0a09537a':
                    raise ValueError('Real calibration hash mismatch')
                send(data); time.sleep(2); measure(label)
        else:
            send((REF/'parameters/real_0x01.bin').read_bytes())
            for label, tx in [('affine_plus24',24),('affine_minus24',-24)]:
                send(tool.build_affine(dict(identity_aff,tx=tx),enable=1)); time.sleep(2); measure(label)
            send(tool.build_affine(identity_aff,enable=0)); time.sleep(2); measure('real_restored')
        log['state']='TRIAL_FINISHED_NOT_PRODUCTION_ACCEPTANCE'
    except Exception as exc:
        log['errors'].append(repr(exc)); log['state']='FAILED'; print('ERROR',repr(exc),flush=True)
        raise
    finally:
        if args.phase=='affine':
            try: send(tool.build_affine(identity_aff,enable=0)); log['affine_restore_sent']=True
            except Exception as exc: log['restore_error']=repr(exc)
        conn.close(); log['end']=datetime.datetime.now().astimezone().isoformat(); save()
        print('EVIDENCE',out,flush=True)

if __name__=='__main__': main()
