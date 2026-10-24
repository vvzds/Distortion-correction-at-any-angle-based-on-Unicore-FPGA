"""Record real CP2102 UART status; optionally apply frozen identity packets."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import sys
import time

BASE=Path('D:/FPGA PDS/yx/DCSjingtaijiaozheng')
HERE=Path(__file__).resolve().parent
sys.path.insert(0,'C:/Users/叶翔/Documents/Codex/2026-10-10/x20/work/host_validation_deps')
sys.path.insert(0,str(BASE/'04_uart_tool'))
import uart_tool as tool
from serial.tools import list_ports

def now(): return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat()

def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--identity',action='store_true')
    mode.add_argument('--real',action='store_true')
    parser.add_argument('--samples',type=int,default=7)
    args=parser.parse_args()
    out=HERE/('uart_'+dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json')
    record=dict(start=now(),state='RUNNING',queries=[],writes=[],programmed=False)
    def save(): out.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    try:
        ports=list(list_ports.comports())
        record['ports']=[dict(port=p.device,vid=p.vid,pid=p.pid,description=p.description) for p in ports]
        matches=[p for p in ports if p.vid==0x10c4 and p.pid==0xea60]
        if len(matches)!=1: raise RuntimeError('Expected exactly one CP2102, found '+str(len(matches)))
        record['port']=matches[0].device
        save()
        with tool.open_serial(record['port']) as connection:
            def query():
                connection.reset_input_buffer()
                request=tool.frame(0x05)
                row=dict(time=now(),elapsed=time.monotonic(),request_hex=request.hex())
                connection.write(request)
                connection.flush()
                status=tool.read_status_frame(connection)
                row.update(status_hex='0x%08X'%status,fw_version=status&255,
                    params_valid=(status>>8)&1,frame_busy=(status>>9)&1,
                    reserved=(status>>10)&63,pub_count=(status>>16)&65535)
                record['queries'].append(row)
                save()
                print(json.dumps(row,ensure_ascii=False),flush=True)
                if row['fw_version']!=0x12 or row['reserved']!=0:
                    raise RuntimeError('Unexpected firmware/status contract')
                return row
            before=query()
            if args.identity or args.real:
                folder=BASE/'03_parameters/parameters'
                parameter_name='real_0x01.bin' if args.real else 'identity_0x01.bin'
                for name in ('gamma_disabled_0x04.bin','affine_disabled_0x02.bin',parameter_name):
                    packet=(folder/name).read_bytes()
                    tool.parse_frame(packet)
                    row=dict(time=now(),file=name,hex=packet.hex(),sha256=hashlib.sha256(packet).hexdigest())
                    written=connection.write(packet)
                    connection.flush()
                    row['bytes_written']=written
                    record['writes'].append(row)
                    save()
                    if written!=len(packet): raise RuntimeError('Short write')
                    time.sleep(.1)
            for i in range(args.samples):
                time.sleep(.5)
                query()
        first,last=record['queries'][0],record['queries'][-1]
        elapsed=last['elapsed']-first['elapsed']
        delta=(last['pub_count']-first['pub_count'])&65535
        record.update(state='COMPLETE',elapsed_s=elapsed,publish_delta=delta,
            observed_publish_per_s=delta/elapsed if elapsed else None,finished=now())
    except Exception as exc:
        record.update(state='FAILED',error=type(exc).__name__+': '+str(exc),finished=now())
    save()
    print(json.dumps(dict(file=str(out),**{k:v for k,v in record.items() if k not in ('queries','ports','writes')}),ensure_ascii=False,indent=2))
    return 0 if record['state']=='COMPLETE' else 1

if __name__=='__main__': raise SystemExit(main())
