"""Archive original G3 SP6.4 evidence and verify unchanged G3 production/tests."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    'g3_snr.txt': (62643, 'B870B6F09E72A89D034CB2E75E798CBF8BD4C85F1585BD7DDC1F2A88714BE66E'),
    'g3_console.log': (190118, '37A1C0235C28A8F7733214DDE14B848C041A061E9D94CE81363CBF7DB85E5F71'),
    'g3_multiseed_summary.csv': (1644, 'B1365817C528EE0DF19171D856709750A450B132344DBF1DD0F8FC1181AA2300'),
    'g3_apm_drm_lutram_utilization.log': (60928, '449D3796D1BE617CC96C805B3DD49F9362A4FB3E267AA9B60E7AFB695EF94A49'),
}


def sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive', type=Path, required=True)
    ap.add_argument('--synthesis-review', type=Path, required=True)
    ap.add_argument('--acceptance-review', type=Path, required=True)
    args = ap.parse_args()
    dest = ROOT / 'verification/design_g3_sp64_20261018'
    dest.mkdir(parents=True, exist_ok=True)
    entries = []
    with zipfile.ZipFile(args.archive) as z:
        assert z.testzip() is None
        names = [m.filename for m in z.infolist() if not m.is_dir()]
        assert len(names) == 4 and set(names) == set(EXPECTED)
        for name in names:
            raw = z.read(name)
            size, expected = EXPECTED[name]
            assert len(raw) == size and sha(raw) == expected, name
            (dest / name).write_bytes(raw)
            assert (dest / name).read_bytes() == raw
            entries.append([name, (dest / name).relative_to(ROOT).as_posix(), size, sha(raw), 'true'])
    for source, name in ((args.synthesis_review, '综合复核记录_设计方.md'),
                         (args.acceptance_review, '接收审查结论_设计方.md')):
        raw = source.read_bytes()
        (dest / name).write_bytes(raw)
        assert (dest / name).read_bytes() == raw
        entries.append([source.name, (dest / name).relative_to(ROOT).as_posix(), len(raw), sha(raw), 'true'])
    with (ROOT / 'verification/g3_sp64_sources_sha256.tsv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t', lineterminator='\n')
        writer.writerow(['original_member', 'archived_path', 'bytes', 'sha256', 'match'])
        writer.writerows(entries)
    snr = (dest / 'g3_snr.txt').read_text(encoding='utf-8-sig')
    assert re.search(r'125\.0000 MHz\s+106\.7008 MHz\s+8\.0000\s+9\.3720\s+-1\.372', snr)
    assert re.search(r'-1\.372\s+-121\.657\s+423\s+10048', snr)
    assert re.search(r'0\.324\s+0\.000\s+0\s+10048', snr)
    assert 'fifo_rd[2]/CLK' in snr and 'o_corr_rd_addr[21]/D' in snr
    assert 'Design Summary : Some Constraints Violated.' in snr
    console = (dest / 'g3_console.log').read_text(encoding='utf-8-sig')
    assert 'Total LUTs: 4299' in console and 'Total Registers: 3744' in console
    assert 'Process "Synthesize" done.' in console
    baseline = '3e50aae'
    paths = git('ls-tree', '-r', '--name-only', baseline, 'source/rtl', 'sim').splitlines()
    assert len(paths) == 25  # four production modules, 21 existing TB/runner files
    checks = []
    for path in paths:
        old = git('rev-parse', baseline + ':' + path)
        current = git('hash-object', path)
        assert old == current, path
        checks.append({'path': path, 'baseline_blob': old, 'current_blob': current, 'unchanged': True})
    receipt = {
        'archive_path': str(args.archive.resolve()),
        'archive_bytes': args.archive.stat().st_size,
        'archive_sha256': sha(args.archive.read_bytes()),
        'report_files': 4, 'original_documents': 2, 'all_archives_byte_exact': True,
        'g3_measurement': {'requested_period_ns': 8, 'setup_wns_ns': -1.372,
                           'setup_tns_ns': -121.657, 'failing_endpoints': 423,
                           'estimated_mhz': 106.7008, 'slow_hold_whs_ns': 0.324,
                           'slow_hold_failing_endpoints': 0, 'LUT': 4299, 'FF': 3744,
                           'APM': 106, 'DRM': 16, 'physical_pnr': 'NOT PROVIDED'},
        'production_and_existing_sim_unchanged': checks,
        'g4_started': False, 'new_simulation_or_synthesis_run': False,
    }
    (ROOT / 'verification/g3_sp64_receipt.json').write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print('PASS: 6 originals byte-exact; SNR/console metrics matched; 4 RTL + 21 existing tests unchanged')
    print('G3 setup WNS=-1.372ns; 125MHz NOT closed; G4 is a proposal only')


if __name__ == '__main__':
    main()
