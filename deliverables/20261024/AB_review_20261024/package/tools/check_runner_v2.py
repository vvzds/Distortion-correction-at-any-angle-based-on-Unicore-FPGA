"""Bookkeeping regression only; does not invoke PDS or simulate RTL."""
from pathlib import Path
import importlib.util, json, tempfile, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runner_v2', ROOT / 'tools/run_synthesis_v2.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
cases = []

def check(name, passed):
    cases.append(dict(name=name, status='PASS' if passed else 'FAIL'))
    if not passed:
        raise RuntimeError(name)

with tempfile.TemporaryDirectory(prefix='runner_fixture_', dir=ROOT / 'evidence') as tmp:
    m.ROOT = Path(tmp)
    p = m.ROOT / 'core/source.v'
    p.parent.mkdir()
    p.write_text('frozen source\n', encoding='utf-8')
    frozen = {'core/source.v': m.sha(p)}
    check('unchanged_input', m.rehash_inputs(frozen) == frozen)
    (p.parent / 'generated.pds').write_text('tool output', encoding='utf-8')
    check('generated_project_does_not_change_fixed_set', m.rehash_inputs(frozen) == frozen)
    p.write_text('modified source\n', encoding='utf-8')
    check('modified_original_input_detected', m.rehash_inputs(frozen) != frozen)
    p.unlink()
    check('missing_original_input_detected', m.rehash_inputs(frozen)['core/source.v'] is None)
    (p.parent / 'compile').mkdir()
    try:
        m.run('core', Path('not_a_tool.exe'), 1, 'fixture')
    except RuntimeError as e:
        check('refuses_existing_native_evidence_before_launch', 'Refusing to overwrite' in str(e))
    else:
        check('refuses_existing_native_evidence_before_launch', False)

cmd = [sys.executable, '-B', '-X', 'utf8', str(ROOT / 'tools/run_synthesis_v2.py'), '--help']
r = subprocess.run(cmd, capture_output=True, text=True)
check('cli_parse', r.returncode == 0 and '--run-label' in r.stdout)
result = dict(status='PASS', scope='RUNNER_BOOKKEEPING_ONLY_NO_PDS_RERUN', cases=cases,
              runner_sha256=m.sha(ROOT / 'tools/run_synthesis_v2.py'), command=cmd,
              cli_exit_code=r.returncode)
(ROOT / 'evidence/runner_v2_check.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
