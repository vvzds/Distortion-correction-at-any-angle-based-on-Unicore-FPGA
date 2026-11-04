"""Start PDS JTAG if needed, program the verified SRAM image, then open preview."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PDS = Path('D:/pango/PDS_2022.2-SP6.4')


def server_ready(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.3):
            return True
    except OSError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM9')
    parser.add_argument('--camera', type=int)
    parser.add_argument('--pds', type=Path, default=PDS)
    parser.add_argument('--server-port', type=int, default=65421)
    args = parser.parse_args()

    if not server_ready(args.server_port):
        server = args.pds/'bin/cdt_js.exe'
        if not server.is_file():
            parser.error(f'PDS JTAG server not found: {server}')
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        subprocess.Popen([str(server), '-port', str(args.server_port),
                          '-work_dir', str(ROOT/'reports/board_runs')],
                         cwd=ROOT, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags)
        deadline = time.monotonic()+20
        while time.monotonic() < deadline and not server_ready(args.server_port):
            time.sleep(.25)
        if not server_ready(args.server_port):
            parser.error('PDS JTAG server did not become ready on the requested port')

    output = ROOT/'reports/board_runs'/datetime.now().strftime('%Y%m%d_%H%M%S_feedback_trial')
    programming = subprocess.run([
        sys.executable, str(ROOT/'tools/program_sram.py'),
        '--manifest', str(ROOT/'release/clean_smooth_manifest.json'),
        '--server-port', str(args.server_port), '--pds', str(args.pds),
        '--output', str(output)], cwd=ROOT)
    if programming.returncode:
        return programming.returncode

    preview = [sys.executable, str(ROOT/'host/board_trial.py'), '--port', args.port]
    if args.camera is not None:
        preview.extend(['--camera', str(args.camera)])
    os.execv(sys.executable, preview)


if __name__ == '__main__':
    raise SystemExit(main())
