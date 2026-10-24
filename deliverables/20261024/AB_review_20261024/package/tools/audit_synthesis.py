"""Reconcile original immutable synthesis receipts; never change their result."""
from pathlib import Path
import hashlib, json, re
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def audit(kind):
    folder = ROOT / 'evidence' / ('synth_' + kind)
    receipt = folder / 'process_receipt.json'
    r = json.loads(receipt.read_text(encoding='utf-8'))
    before, after = r['inputs_before'], r['inputs_after']
    fixed_set_matches = all(after.get(k) == v for k, v in before.items())
    current = {k: sha(ROOT / k) if (ROOT / k).is_file() else None for k in before}
    additions = {k: v for k, v in after.items() if k not in before}
    artifact_errors = []
    for item in r['artifacts']:
        p = ROOT / item['file']
        if not p.is_file() or p.stat().st_size != item['bytes'] or sha(p) != item['sha256']:
            artifact_errors.append(item['file'])
    log = folder / 'console.log'
    text = log.read_text(encoding='utf-8', errors='replace')
    tool = Path(r['command'][0])
    tool_ok = tool.is_file() and sha(tool) == r['tool_sha256_before'] == r['tool_sha256_after']
    ok = (r['exit_code'] == 0 and 'Process "Synthesize" done.' in text
          and not re.search(r'(?m)^E:', text) and fixed_set_matches
          and current == before and not artifact_errors and tool_ok
          and sha(log) == r['console_sha256']
          and set(additions) == {f'{kind}/ab_r1r4_{kind}.pds'}
          and all(sha(ROOT / k) == v for k, v in additions.items()))
    snr = next((ROOT / kind / 'synthesize').glob('*.snr'))
    snr_text = snr.read_text(encoding='utf-8', errors='replace')
    paths = re.split(r'(?=Startpoint\s*:)', snr_text)
    group = 'undistort_core|clk' if kind == 'core' else 'ddrphy_sysclk'
    worst = next(p for p in paths if re.search(r'Path Group\s*:\s*' + re.escape(group) + r'\s*\n', p)
                 and re.search(r'Path Type\s*:\s*max', p))
    endpoints = [line for line in worst.splitlines() if re.match(r'Startpoint|Endpoint|Path Group|Path Type', line)]
    data = dict(kind=kind, audit_utc=datetime.now(timezone.utc).isoformat(),
                raw_receipt_sha256=sha(receipt), raw_status=r['status'],
                raw_receipt_preserved=True, pds_exit_code=r['exit_code'],
                original_input_count=len(before), fixed_input_set_matches_recorded_after=fixed_set_matches,
                fixed_input_set_matches_current=current == before,
                newly_generated_project_files=additions,
                artifact_count=len(r['artifacts']), artifact_errors=artifact_errors,
                console_sha_matches=sha(log) == r['console_sha256'], tool_sha_matches=tool_ok,
                audit_status='PASS' if ok else 'FAIL',
                synthesis_status='COMPLETE' if ok else 'UNVERIFIED',
                timing_125mhz='FAIL', pnr='NOT_RUN', bitstream='NOT_GENERATED', board='PAUSED_BY_USER',
                snr=dict(file=snr.relative_to(ROOT).as_posix(), sha256=sha(snr),
                         version_header=snr_text.splitlines()[0], worst_path=endpoints),
                reason='v1 compared enumerated input sets; PDS added a generated .pds. All originally frozen inputs and recorded artifacts are independently checked here. No original receipt is rewritten; synthesis completion does not imply timing PASS.')
    out = folder / 'fixed_input_audit.json'
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return data

if __name__ == '__main__':
    results = [audit(kind) for kind in ('core', 'host')]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(r['audit_status'] == 'PASS' for r in results) else 1)
