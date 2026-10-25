"""模块2实机证据采集；先查询，版本匹配后才写参数，finally恢复。"""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,os,sys,threading,time,traceback,uuid
W=Path(__file__).resolve().parent
sys.path.insert(0,str(W.parent/'host_validation_deps'))
sys.path.insert(0,str(W.parent/'affine_track_loop_review_20261020'))
import cv2,numpy as np
from serial.tools import list_ports
from camera_devices import enumerate_cameras
spec=importlib.util.spec_from_file_location('approved_uart',W/'reference/uart_tool_tlimfix.py')
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
EXPECTED_TOOL='043f8076f3ee9b810081fa337b6ed0cdffa85131ee4a3c04f409534960331a57'
PHOTO=Path('C:/Users/叶翔/Desktop/photo/module2_uart_20261025')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()

def decode_status(v):
    if v&255!=0x12:raise ValueError('Unexpected firmware version: %08x'%v)
    if v&0xfc00:raise ValueError('Reserved status bits are nonzero')
    return dict(raw='%08x'%v,fw=v&255,params_valid=(v>>8)&1,busy=(v>>9)&1,pub_count=v>>16)

def pub_delta(new,old):
    delta=(new-old)&65535
    if delta>=32768:raise ValueError('Publication count reset or ambiguous wrap')
    return delta

class WireLog:
    def __init__(self,s,path):self.s=s;self.f=path.open('w',encoding='utf-8');self.records=[]
    def __getattr__(self,n):return getattr(self.s,n)
    def record(self,d,b,**fields):
        row=dict(time=now(),monotonic_ns=time.monotonic_ns(),direction=d,hex=b.hex(),**fields)
        self.records.append(row);self.f.write(json.dumps(row,ensure_ascii=False)+'\n');self.f.flush()
    def read(self,n=1):
        b=self.s.read(n)
        if b:self.record('RX',b)
        return b
    def write(self,b):
        start=time.monotonic_ns();n=self.s.write(b);self.record('TX',b,written=n,start_monotonic_ns=start)
        if n!=len(b):raise IOError('Partial serial write')
        return n
    def close(self):
        try:self.s.close()
        finally:self.f.close()

def query(c):
    c.write(tool.frame(5));c.flush()
    return dict(time=now(),monotonic_ns=time.monotonic_ns(),**decode_status(tool.read_status_frame(c)))

class Capture:
    def __init__(self,index):
        self.cap=cv2.VideoCapture(index,cv2.CAP_DSHOW)
        if not self.cap.isOpened():raise IOError('Hagibis unavailable; release OBS')
        for p,v in [(cv2.CAP_PROP_FRAME_WIDTH,1920),(cv2.CAP_PROP_FRAME_HEIGHT,1080),(cv2.CAP_PROP_FPS,30),
                    (cv2.CAP_PROP_FOURCC,cv2.VideoWriter_fourcc(*'MJPG'))]:self.cap.set(p,v)
        self.negotiated=dict(width=self.cap.get(3),height=self.cap.get(4),fps=self.cap.get(5),fourcc=int(self.cap.get(6)))
        self.stop=threading.Event();self.lock=threading.Lock();self.latest=None;self.error=None;self.seq=0
        self.thread=threading.Thread(target=self.read,daemon=True);self.thread.start()
    def read(self):
        try:
            while not self.stop.is_set():
                ok,img=self.cap.read()
                if not ok:raise IOError('Video read failed')
                if img.shape[:2]!=(1080,1920):raise IOError('Unexpected dimensions')
                with self.lock:
                    self.seq+=1;self.latest=(time.monotonic_ns(),now(),self.seq,img)
        except Exception:self.error=traceback.format_exc()
    def snapshot(self,after=0):
        with self.lock:
            if self.error:raise IOError(self.error)
            if self.latest is None or self.latest[0]<=after:raise IOError('No fresh capture transport sample')
            ns,t,seq,img=self.latest
            return ns,t,seq,img.copy()
    def close(self):
        self.stop.set();self.thread.join(timeout=3)
        if self.thread.is_alive():raise IOError('Capture reader did not stop cleanly')
        self.cap.release()

def select_hardware():
    ports=list(list_ports.comports());p=[p for p in ports if p.vid==0x10c4 and p.pid==0xea60]
    if len(p)!=1:raise ValueError('Need one CP2102 port')
    return p[0],ports

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--query-only',action='store_true');ap.add_argument('--capture-probe',action='store_true')
    args=ap.parse_args()
    run=datetime.datetime.now().strftime('%H%M%S')+'_'+uuid.uuid4().hex[:6]
    out=W/'evidence'/('board_'+run);out.mkdir()
    photos=PHOTO/run
    r=dict(start=now(),scope='MODULE2_PARAMETERS_UART',stages=[],errors=[],restoration={},parameters_sent=False,
           bitstream_identity='LOCAL_FILE_SHA_AND_FW_STATUS_COMPATIBILITY_ONLY_SRAM_NOT_READ_BACK',internal_atomicity='RTL_SIMULATION_ONLY')
    c=None;cam=None;changed=False
    def save():
        (out/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    def send(packet,label):
        nonlocal changed
        tool.parse_frame(packet);changed=True;r['parameters_sent']=True
        c.write(packet);c.flush();r.setdefault('writes',[]).append(dict(label=label,time=now(),hex=packet.hex()))
        # 不把串口写成功当作板端ACK。
        save()
    def restore():
        for name in ('gamma_disabled_0x04.bin','affine_disabled_0x02.bin','real_0x01.bin'):
            send((W/'reference/parameters'/name).read_bytes(),'restore_'+name)
    def settle(stage,start_count):
        begin=time.monotonic();stage['statuses']=[]
        while True:
            st=query(c);stage['statuses'].append(st);save()
            if not st['params_valid']:raise ValueError('Live parameters invalid after legal write')
            delta=pub_delta(st['pub_count'],start_count)
            if time.monotonic()-begin>=8 and delta>=3:
                stage['fresh_publications_at_least']=delta;return st
            if time.monotonic()-begin>30:raise TimeoutError('No new corrected frames after switch')
            time.sleep(.5)
    def stage(name,packets=(),malformed=()):
        st=dict(name=name,start=now(),captures=[]);r['stages'].append(st)
        old=query(c)['pub_count'];ns=time.monotonic_ns()
        for label,packet in packets:send(packet,label)
        for label,packet in malformed:
            # 仅固定、已在RTL验证的错误校验和/旧长度；不能走合法包parse入口。
            c.write(packet);c.flush();r.setdefault('writes',[]).append(dict(label=label,time=now(),hex=packet.hex(),deliberately_malformed=True));save()
        settle(st,old)
        for i in range(3):
            timestamp,t,seq,img=cam.snapshot(ns)
            q=photos/('%s_%02d.png'%(name,i));q.write_bytes(cv2.imencode('.png',img)[1].tobytes())
            gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
            st['captures'].append(dict(path=str(q),sha256=sha(q),timestamp=t,monotonic_ns=timestamp,transport_seq=seq,
                 shape=list(img.shape),mean_bgr=[float(x) for x in img.mean(axis=(0,1))],gray_std=float(gray.std())))
            ns=timestamp;save();time.sleep(.4)
        st['end']=now();st['state']='CAPTURED_NOT_YET_ANALYZED';save()
        print('Captured:',name,flush=True)
    try:
        if sha(W/'reference/uart_tool_tlimfix.py')!=EXPECTED_TOOL:raise ValueError('Tool hash mismatch')
        p,ports=select_hardware();r['ports']=[dict(device=x.device,description=x.description,vid=x.vid,pid=x.pid) for x in ports]
        c=WireLog(tool.open_serial(p.device),out/'wire.jsonl')
        r['initial_status']=query(c);save()
        if args.query_only:r['state']='QUERY_PASS_NO_PARAMETER_WRITES';return
        cameras=enumerate_cameras();r['cameras']=cameras
        cams=[x for x in cameras if x.get('FriendlyName')=='Hagibis' and 'vid_345f&pid_2131' in x.get('DevicePath','').lower()]
        if len(cams)!=1:raise ValueError('Need unique Hagibis')
        cam=Capture(cams[0]['index']);r['capture_transport']=cam.negotiated
        time.sleep(3);_,_,_,img=cam.snapshot()
        photos.mkdir(parents=True)
        (photos/'probe.png').write_bytes(cv2.imencode('.png',img)[1].tobytes())
        # 复位后合法状态为valid=0/count=0，尚未下发参数自然没有校正画面。
        # 只读probe保持只读；完整测试允许以已冻结真实参数完成初始化。
        if not args.capture_probe and r['initial_status']['params_valid']==0:
            r['bootstrap_reason']='Reset or invalid parameter state; compatible FW replied; load known legal real group'
            restore();bootstrap=dict(name='bootstrap',statuses=[])
            settle(bootstrap,r['initial_status']['pub_count']);r['bootstrap']=bootstrap
            _,_,_,img=cam.snapshot()
        gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
        if gray.std()<8 or gray.mean()<8:raise ValueError('Black or untextured input; no parameter writes')
        if args.capture_probe:
            r['state']='CAPTURE_PROBE_PASS_NO_PARAMETER_WRITES';return
        restore();stage('real_baseline')
        stage('identity', [('identity', (W/'reference/parameters/identity_0x01.bin').read_bytes())])
        stage('real_restored', [('real', (W/'reference/parameters/real_0x01.bin').read_bytes())])
        aff=dict(a11=1,a12=0,a21=0,a22=1,tx=24,ty=0)
        stage('affine_tx24',[('affine24',tool.build_affine(aff,enable=1))])
        stage('affine_off',[('affine_off',(W/'reference/parameters/affine_disabled_0x02.bin').read_bytes())])
        stage('gamma_identity', [('gamma_off',tool.build_mode(0))]+[
            ('identity_lut_%d'%ch,tool.build_gamma(ch,list(range(256)))) for ch in range(3)]+[('gamma_on',tool.build_mode(1))])
        stage('gamma_dim',[('gamma_off',tool.build_mode(0))]+[
            ('dim_lut_%d'%ch,tool.build_gamma(ch,[int(round(v*.60)) for v in range(256)])) for ch in range(3)]+[('gamma_on',tool.build_mode(1))])
        stage('gamma_off',[('gamma_off',tool.build_mode(0))])
        bad=bytearray(tool.build_mode(1));bad[-1]^=1
        stage('rejected_frames',malformed=[('bad_checksum_mode_on',bytes(bad)),('legacy_length_empty',bytes.fromhex('aa55021800'))])
        r['state']='CAPTURE_SEQUENCE_COMPLETED_ANALYSIS_REQUIRED'
    except Exception:
        r['errors'].append(traceback.format_exc());r['state']='FAILED_OR_INCOMPLETE'
    finally:
        if c and changed:
            try:
                restore();r['restoration']['packets_sent']=True
                initial=query(c);s=dict(name='restore_final',statuses=[])
                settle(s,initial['pub_count']);r['restoration'].update(status=s['statuses'][-1],fresh_publications_at_least=s['fresh_publications_at_least'],verified_publishing=True,
                     gamma_enable='OFF_REQUESTED_IMAGE_EVIDENCE_SEPARATE',affine_enable='OFF_REQUESTED_IMAGE_EVIDENCE_SEPARATE',distortion='REAL_PACKET_SENT')
            except Exception:r['restoration']['error']=traceback.format_exc();r['state']='RESTORATION_NOT_CONFIRMED'
        if cam:
            try:cam.close()
            except Exception:r['errors'].append(traceback.format_exc())
        if c:c.close()
        r['finished']=now();r['photos']=str(photos);save()
        print(json.dumps(dict(state=r['state'],out=str(out),errors=r['errors'],restoration=r['restoration']),ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
