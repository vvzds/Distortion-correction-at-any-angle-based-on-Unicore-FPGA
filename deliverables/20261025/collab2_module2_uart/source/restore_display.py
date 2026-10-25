"""手动运行的参数恢复入口，不编译/烧录，不改变上电默认值。"""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,sys,time
W=Path(__file__).resolve().parent
# 本机随附入口使用已安装的依赖；其他电脑可用Python3.8+安装pyserial。
for p in (W/'deps',W.parent/'host_validation_deps',
    Path('C:/Users/叶翔/Documents/Codex/2026-10-10/x20/work/host_validation_deps')):
    if p.is_dir():sys.path.insert(0,str(p))
spec=importlib.util.spec_from_file_location('approved_uart',W/'reference/uart_tool_tlimfix.py')
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
EXPECTED={
 'gamma_disabled_0x04.bin':'',
 'affine_disabled_0x02.bin':'',
 'real_0x01.bin':'1ac17c4bea8947d1e4a84f50a7eaaf46c0b1d90dd4b8e8ba880bc01e0a09537a'}

def main():
    ap=argparse.ArgumentParser(description='Restore calibrated display through USB-UART')
    ap.add_argument('--apply',action='store_true',help='Actually send packets; default only show plan')
    args=ap.parse_args()
    if sha(W/'reference/uart_tool_tlimfix.py')!='043f8076f3ee9b810081fa337b6ed0cdffa85131ee4a3c04f409534960331a57':
        raise ValueError('Approved tool SHA mismatch')
    names=list(EXPECTED);packets=[(W/'reference/parameters'/n).read_bytes() for n in names]
    for name,packet in zip(names,packets):
        tool.parse_frame(packet)
        if EXPECTED[name] and hashlib.sha256(packet).hexdigest()!=EXPECTED[name]:raise ValueError('Real parameter SHA mismatch')
    if packets[0]!=tool.build_mode(0):raise ValueError('Gamma off packet mismatch')
    if packets[1]!=tool.build_affine(dict(a11=1,a12=0,a21=0,a22=1,tx=0,ty=0),enable=0):raise ValueError('Affine off packet mismatch')
    print('Plan: query FW 0x12; Gamma OFF; Affine OFF; REAL calibration; verify new publications.')
    if not args.apply:
        print('DRY RUN ONLY. Use --apply to send to the board.');return 0
    from serial.tools import list_ports
    ports=[p for p in list_ports.comports() if p.vid==0x10c4 and p.pid==0xea60]
    if len(ports)!=1:raise ValueError('Need exactly one CP2102 USB-UART port; JTAG COM9/COM10 are not UART')
    log=dict(start=datetime.datetime.now().astimezone().isoformat(),port=ports[0].device,wire=[],state='RUNNING')
    out=W/'runtime_logs';out.mkdir(exist_ok=True)
    path=out/(datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json')
    class Wire:
        def __init__(self,s):self.s=s
        def __getattr__(self,n):return getattr(self.s,n)
        def save(self,d,b,**kw):
            log['wire'].append(dict(time=datetime.datetime.now().astimezone().isoformat(),monotonic_ns=time.monotonic_ns(),direction=d,hex=b.hex(),**kw))
            path.write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8')
        def write(self,b):
            n=self.s.write(b);self.save('TX',b,written=n)
            if n!=len(b):raise IOError('Partial UART write')
            return n
        def read(self,n=1):
            b=self.s.read(n)
            if b:self.save('RX',b)
            return b
    c=Wire(tool.open_serial(ports[0].device))
    def query():
        c.write(tool.frame(5));c.flush();s=tool.read_status_frame(c)
        if s&255!=0x12 or s&0xfc00:raise ValueError('Unexpected firmware status: %08x'%s)
        return s
    try:
        initial=query();log['initial_status']='%08x'%initial
        for packet in packets:c.write(packet);c.flush()
        begin=time.monotonic()
        while True:
            status=query();delta=((status>>16)-(initial>>16))&65535
            if delta>=32768:raise ValueError('Publication count reset during operation')
            if status&256 and delta>=3:
                log.update(state='PARAMETERS_SENT_AND_NEW_FRAMES_OBSERVED',final_status='%08x'%status,new_publications=delta)
                print('PASS: real calibration sent; new frames observed. HDMI remains 1080P30.')
                print('This is status evidence; inspect the monitor to confirm the intended scene.');return 0
            if time.monotonic()-begin>30:raise TimeoutError('No new frames; check FPGA bitstream and camera')
            time.sleep(.5)
    except Exception as e:
        log.update(state='FAILED',error=repr(e));raise
    finally:
        c.close();log['end']=datetime.datetime.now().astimezone().isoformat()
        path.write_text(json.dumps(log,ensure_ascii=False,indent=2),encoding='utf-8');print('Log:',path)

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:print('ERROR:',e);sys.exit(1)
