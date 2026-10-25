"""无串口、无图像重处理：核验真实收发字节、恢复链与仿真来源。"""
from pathlib import Path
import hashlib,json,struct
W=Path(__file__).resolve().parent
F=W/'evidence/board_193339_737475'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def audit():
    r=json.loads((F/'result.json').read_text(encoding='utf-8'))
    assert r['state']=='CAPTURE_SEQUENCE_COMPLETED_ANALYSIS_REQUIRED' and not r['errors']
    m=json.loads((F/'analysis/metrics.json').read_text(encoding='utf-8'))
    assert m['state']=='ENGINEERING_OBSERVATIONS_PASS' and all(m['engineering_checks'].values())
    sim=W/'evidence/sim_c3495e1edd'
    sr=json.loads((sim/'receipt.json').read_text(encoding='utf-8'))
    assert sr['status']=='PASS' and len(sr['cases'])==2
    for t in sr['cases']:
        assert t['passed'] and t['exit']==0
        assert sha(sim/(t['top']+'.log'))==t['log_sha256']
        assert sha(W/'reference/param_mgr.v')==t['rtl_sha256']
        tb=W/('reference/param_mgr_tb.v' if t['top']=='param_mgr_tb' else 'tb/param_mgr_extended_tb.v')
        assert sha(tb)==t['tb_sha256']
    wire=[json.loads(s) for s in (F/'wire.jsonl').read_text(encoding='utf-8').splitlines()]
    q=None;buf=bytearray();queries=[];commands=[];last_ns=0
    deliberately_bad={bytes.fromhex('aa5504040100000000'),bytes.fromhex('aa55021800')}
    for x in wire:
        ns=x['monotonic_ns'];assert ns>=last_ns;last_ns=ns
        p=bytes.fromhex(x['hex'])
        if x['direction']=='TX':
            assert x['written']==len(p) and x['start_monotonic_ns']<=ns
            assert p[:2]==b'\xaa\x55'
            if p==bytes.fromhex('aa55050000'):
                assert q is None;q=x;buf.clear()
            else:
                assert q is None
                if p not in deliberately_bad:
                    cmd=p[2];target={1:32,2:25,3:256,4:4}[cmd]
                    assert len(p)==target+5 and sum(p[4:-1])&255==p[-1]
                    assert p[3] in range(3) if cmd==3 else p[3]==target
                commands.append(dict(hex=p.hex(),time=x['time'],deliberately_bad=p in deliberately_bad))
        elif x['direction']=='RX':
            assert q is not None;buf.extend(p)
            assert len(buf)<=9
            if len(buf)==9:
                assert buf[:4]==bytes.fromhex('aa550504') and sum(buf[4:8])&255==buf[8]
                v=struct.unpack('<I',buf[4:8])[0]
                assert v&255==0x12 and not v&0xfc00
                queries.append(dict(tx_time=q['time'],rx_completed_time=x['time'],
                    elapsed_ms=(ns-q['start_monotonic_ns'])/1e6,status='%08x'%v,pub_count=v>>16,valid=(v>>8)&1))
                q=None;buf.clear()
        else:raise ValueError('Unknown direction')
    assert q is None and len(commands)==len(r['writes'])
    assert [x['hex'] for x in commands]==[x['hex'] for x in r['writes']]
    expected=[(W/'reference/parameters'/name).read_bytes().hex() for name in
       ('gamma_disabled_0x04.bin','affine_disabled_0x02.bin','real_0x01.bin')]
    assert [x['hex'] for x in commands[-3:]]==expected
    assert sum(x['deliberately_bad'] for x in commands)==2
    images=0
    for s in r['stages']:
        assert len(s['captures'])==3 and s['fresh_publications_at_least']>=3
        for f in s['captures']:
            assert sha(Path(f['path']))==f['sha256'];images+=1
    assert images==27 and r['restoration']['verified_publishing']
    statuses=[r['initial_status']]+r['bootstrap']['statuses']
    statuses += [t for s in r['stages'] for t in s['statuses']]
    statuses.append(r['restoration']['status'])
    for a,b in zip(statuses,statuses[1:]):assert 0<=((b['pub_count']-a['pub_count'])&65535)<32768
    span=(wire[-1]['monotonic_ns']-wire[0]['start_monotonic_ns'])/1e9
    rates=[]
    for s in r['stages']:
        a,b=s['statuses'][0],s['statuses'][-1]
        elapsed=(b['monotonic_ns']-a['monotonic_ns'])/1e9
        rates.append(dict(stage=s['name'],elapsed_s=elapsed,count_delta=(b['pub_count']-a['pub_count'])&65535,
            observed_publications_per_second=((b['pub_count']-a['pub_count'])&65535)/elapsed))
    result=dict(state='PASS',wire_rows=len(wire),queries=len(queries),parameter_writes=len(commands),
        deliberate_bad_frames=2,captures=images,span_seconds=span,
        first_status=queries[0]['status'],last_status=queries[-1]['status'],
        count_first=queries[0]['pub_count'],count_last=queries[-1]['pub_count'],
        mixed_mode_average_publications_per_second=(queries[-1]['pub_count']-queries[0]['pub_count'])/span,
        per_stage_rates=rates,
        restoration_payloads_match=True,raw_wire_sha256=sha(F/'wire.jsonl'),queries_detail=queries,
        limitation='Host software timestamps/bytes; not UART pin-level timing or direct live-parameter readback.')
    (W/'evidence/evidence_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='queries_detail'},ensure_ascii=False,indent=2))

if __name__=='__main__':audit()
