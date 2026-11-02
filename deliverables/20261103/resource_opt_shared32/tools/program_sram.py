"""Hash-check and program the released FPGA image into SRAM using PDS.

Requires an already running PDS JTAG server and the attached PG2L100H board.
Uses normal JTAG configuration (program=0), validated on this board. Does not
write Flash or read configuration status after programming.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--server-port', type=int, default=65421)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--pds', type=Path, default=Path('D:/pango/PDS_2022.2-SP6.4'))
    p.add_argument('--manifest', type=Path, default=ROOT/'release/manifest.json')
    args = p.parse_args()
    manifest = json.loads(args.manifest.read_text())
    bitstream = ROOT/manifest['bitstream']
    digest = hashlib.sha256(bitstream.read_bytes()).hexdigest()
    if digest != manifest['sha256']:
        p.error('Released bitstream hash mismatch')
    if args.output.exists():
        p.error('Use a new evidence directory')
    args.output.mkdir(parents=True)
    # ID is checked before mutation. Device index 0 is the tested single-FPGA chain.
    probe = f'''cfg_set_tcl_break -flag true
cfg_connect -ip 127.0.0.1 -port {args.server_port}
cfg_set_cable_property -index 0 -freq 10Mhz
cfg_scan_chain
cfg_read_device_property -mode 0 -device_index 0
cfg_disconnect
cfg_close
'''
    def run(name, script):
        source = args.output/f'{name}.tcl'
        source.write_text(script, encoding='ascii')
        done = subprocess.run([str(args.pds/'bin/cdt_cfg_shell.exe'), '-file',
            source.name, '-work_dir', args.output.resolve().as_posix()],
            cwd=args.output.resolve(),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
        (args.output/f'{name}.txt').write_bytes(done.stdout)
        text = done.stdout.decode('utf8', errors='replace')
        if done.returncode or any(s.lstrip().startswith('E:') for s in text.splitlines()):
            raise RuntimeError(f'PDS {name} failed; see raw evidence')
        return text
    receipt = dict(bitstream_sha256=digest, flash_written=False, programmed=False,
                   program_properties=0, device='PG2L100H')
    try:
        identity = run('probe', probe)
        if 'PG2L100H' not in identity or '0x00602899' not in identity:
            raise RuntimeError('Unexpected FPGA identity; programming stopped')
        script = probe.replace('cfg_read_device_property -mode 0 -device_index 0\n',
            f'cfg_assign_file -file {bitstream.as_posix()} -device_index 0\n'
            'cfg_set_device_property -device_index 0 -program 0 -readback 0\n'
            'cfg_program -device_index 0\n')
        output = run('program', script)
        receipt['programmed'] = 'The done bit is 1' in output and 'COMMAND[Program] execute successfully' in output
        if not receipt['programmed']:
            raise RuntimeError('PDS did not confirm successful programming and done=1')
    except Exception as exc:
        receipt['error'] = f'{type(exc).__name__}: {exc}'
    (args.output/'program_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(receipt,indent=2))
    if not receipt['programmed']:
        sys.exit(1)


if __name__ == '__main__':
    main()
