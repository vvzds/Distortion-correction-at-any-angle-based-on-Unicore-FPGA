"""Verify shipped hashes and portable PDS input references; no extra modules needed."""
import hashlib
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
BIT_HASH = 'ff98eb4f5f8c0b47db29f7fe318400441ef64585a500d783c63360799a830565'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_inputs():
    project = ROOT / '01_fpga'
    text = (project / 'run_host.pds').read_text(encoding='utf-8-sig')
    refs = set(re.findall(r'\(_(?:file|ip|ip_source_item)\s+"([^"]+)"', text))
    script = (project / 'run_host.tcl').read_text(encoding='utf-8-sig')
    refs.update(re.findall(r'add_(?:design|constraint)\s+"([^"]+)"', script))
    for source in (project / 'source').rglob('*'):
        if source.suffix in ('.v', '.vh'):
            # Legacy RTL comments can be GBK; include directives are ASCII.
            refs.update(re.findall(r'`include\s+"([^"]+)"', source.read_bytes().decode('latin1')))
    missing = sorted(ref for ref in refs if not (project / ref).is_file())
    assert not missing, 'Missing project inputs: ' + repr(missing)
    bit = project / 'bitstream' / 'hdmi_ddr_ov5640_top.sbit'
    assert digest(bit) == BIT_HASH, 'Unexpected bitstream hash'
    return len(refs)


def main():
    count = 0
    for line in (ROOT / 'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
        expected, relative = line.split('  ', 1)
        path = ROOT / relative
        assert path.is_file(), 'Missing package file: ' + relative
        assert digest(path) == expected, 'Modified package file: ' + relative
        count += 1
    refs = check_inputs()
    print('PASS: %d shipped hashes; %d project input references; C50 bitstream matches.' % (count, refs))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('FAIL:', exc, file=sys.stderr)
        sys.exit(1)
