"""Explicit-port board test with raw UART journal and published-frame measurement.

Does not program hardware. Camera access requires --capture. Run only after programming the
bitstream identified by release/manifest.json; SHA records the intended file,
and is not a readback of the device configuration.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
from protocol import Connection
from model import load_calibration, affine, preflight
from control import covering_zoom


class JournalSerial:
    def __init__(self, serial, stream):
        self.device, self.stream = serial, stream

    @property
    def in_waiting(self):
        return self.device.in_waiting

    def record(self, direction, data):
        if data:
            self.stream.write(json.dumps(dict(monotonic=time.monotonic(),
                utc=datetime.now(timezone.utc).isoformat(), direction=direction,
                hex=data.hex())) + '\n')
            self.stream.flush()

    def read(self, count):
        data = self.device.read(count)
        self.record('RX', data)
        return data

    def write(self, data):
        count = self.device.write(data)
        self.record('TX', data[:count])
        return count

    def close(self):
        self.device.close()


def healthy(state):
    return not (state['core_fault'] or state['write_fault'] or state['overflow_tiles'])


def capture_scene(directory):
    import cv2
    from cv2_enumerate_cameras import enumerate_cameras
    cameras = [c for c in enumerate_cameras(cv2.CAP_DSHOW)
               if c.name == 'Hagibis' and 'vid_345f' in c.path.lower()]
    if len(cameras) != 1:
        raise RuntimeError('Hagibis capture device identity is not unique')
    camera = cameras[0]
    directory.mkdir()
    cap = cv2.VideoCapture(camera.index, cv2.CAP_DSHOW)
    evidence = dict(name=camera.name, path=camera.path, backend='DSHOW', images=[])
    try:
        if not cap.isOpened():
            raise RuntimeError('Could not open Hagibis')
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        cap.set(cv2.CAP_PROP_FPS, 30)
        for index in range(24):
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError('Hagibis frame read failed')
            if index >= 21:
                path = directory / f'frame_{index}.png'
                if not cv2.imwrite(str(path), frame):
                    raise RuntimeError('Capture image could not be saved')
                evidence['images'].append(dict(file=str(path.resolve()),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    monotonic=time.monotonic(), shape=list(frame.shape),
                    mean=float(frame.mean()), std=float(frame.std())))
        evidence['nominal_fps'] = cap.get(cv2.CAP_PROP_FPS)
    finally:
        cap.release()
    evidence['all_nonblack_1080p'] = all(i['shape'] == [1080,1920,3] and
        i['std'] > 1 and i['mean'] > 1 for i in evidence['images'])
    return evidence


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', required=True)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--seconds', type=float, default=10)
    p.add_argument('--probe-only', action='store_true')
    p.add_argument('--capture', action='store_true', help='Briefly open only the identified Hagibis for each scene')
    p.add_argument('--checker-only', action='store_true', help='Capture raw/calibrated/raw checker scenes')
    p.add_argument('--worst-case', action='store_true', help='Measure 45 degree zoom=1 instead of the scene suite')
    p.add_argument('--sweep', action='store_true', help='Exercise frame-atomic commands at 15 degree intervals through 345 degrees')
    args = p.parse_args()
    if args.seconds < 2:
        p.error('--seconds must be at least 2')
    if sum((args.worst_case, args.sweep, args.checker_only)) > 1:
        p.error('Choose either --worst-case or --sweep')
    if args.checker_only and not args.capture:
        p.error('--checker-only requires --capture')
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / 'uart_test.json'
    if target.exists():
        p.error('Use a new output directory to preserve previous evidence')
    manifest = json.loads((ROOT / 'release/manifest.json').read_text())
    actual = hashlib.sha256((ROOT / manifest['bitstream']).read_bytes()).hexdigest()
    if actual != manifest['sha256']:
        raise RuntimeError('Release bitstream hash mismatch')
    result = dict(port=args.port, utc=datetime.now(timezone.utc).isoformat(),
                  intended_bitstream_sha256=actual, stages=[], passed=False,
                  programming_verified_by_this_script=False)
    runner = Path(__file__).read_bytes()
    (args.output / 'runner_snapshot.py').write_bytes(runner)
    result['runner_sha256'] = hashlib.sha256(runner).hexdigest()
    link = None
    last = None
    defaults = None
    try:
        with (args.output / 'uart_raw.jsonl').open('x', encoding='utf-8') as journal:
            link = Connection(args.port)
            link.serial = JournalSerial(link.serial, journal)
            last = link.status()
            result['initial_status'] = last
            if not healthy(last):
                raise RuntimeError('Initial FPGA fault/overflow; preserving state')
            if args.probe_only:
                result['identity_confirmed'] = True
                return
            c = load_calibration(ROOT / 'calibration/ov5640_1080p.json')
            specs = [('default_0_linear', 0, False, 0, 0, 0, False),
                     ('rotate_45_crop', 45, True, 0, 0, 0, False),
                     ('rotate_90_crop', 90, True, 0, 0, 0, False),
                     ('affine_17_crop', 17, True, 24, -16, .05, False),
                     ('default_0_gamma', 0, False, 0, 0, 0, True)]
            if args.checker_only:
                raw = dict(c, k1=0., k2=0., p1=0., p2=0.)
                specs = [('raw_before', 0, False, 0, 0, 0, False),
                         ('corrected', 0, False, 0, 0, 0, False),
                         ('raw_return', 0, False, 0, 0, 0, False)]
            elif args.worst_case:
                specs = [('rotate_45_no_crop', 45, False, 0, 0, 0, False)]
            if args.sweep:
                specs = [(f'sweep_{angle:03d}', angle, False, 0, 0, 0, False)
                         for angle in range(0, 360, 15)]
            defaults, _ = preflight(c, affine(0, 1, 0, 0, 0), True)
            for name, angle, crop, tx, ty, shear, gamma in specs:
                zoom = covering_zoom(c, angle, tx, ty, shear) if crop else 1
                calibration = raw if args.checker_only and name != 'corrected' else c
                regs, report = preflight(calibration, affine(angle, zoom, tx, ty, shear), gamma)
                stage = dict(name=name, angle=angle, zoom=zoom, tx=tx, ty=ty,
                             shear=shear, adaptive_gamma=gamma, preflight=report,
                             registers=list(map(int, regs)), samples=[])
                result['stages'].append(stage)
                last = link.configure(regs)
                stage['activated_status'] = last
                # Flush at least two camera periods after parameter activation.
                time.sleep(.15)
                if args.capture:
                    stage['capture'] = capture_scene(args.output / name)
                    state = link.status()
                    stage['after_capture_status'] = state
                    if state['active_sequence'] != last['active_sequence']:
                        raise RuntimeError('Parameters changed during capture')
                deadline = time.monotonic() + args.seconds
                while True:
                    before = time.monotonic()
                    last = link.status()
                    after = time.monotonic()
                    stage['samples'].append(dict(monotonic=(before+after)/2,
                        roundtrip_seconds=after-before, **last))
                    if not healthy(last):
                        raise RuntimeError('FPGA fault/overflow; preserving state')
                    if after >= deadline:
                        break
                    time.sleep(.5)
                first, final = stage['samples'][0], stage['samples'][-1]
                elapsed = final['monotonic'] - first['monotonic']
                frames = (final['frames'] - first['frames']) & 0xffffffff
                stage.update(elapsed_seconds=elapsed, new_frames=frames,
                    actual_new_frame_fps=frames/elapsed,
                    passed=frames/elapsed >= 29.5 and all(healthy(s) for s in stage['samples']))
                target.write_text(json.dumps(result, indent=2), encoding='utf-8')
                print(json.dumps({k:stage[k] for k in ['name','new_frames','elapsed_seconds','actual_new_frame_fps','passed']}), flush=True)
            result['restored_status'] = link.configure(defaults)
            result['passed'] = all(s['passed'] for s in result['stages'])
    except Exception as exc:
        result['error'] = f'{type(exc).__name__}: {exc}'
        print(result['error'], file=sys.stderr)
    finally:
        if link is not None:
            link.close()
        target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    if not args.probe_only and not result['passed']:
        raise SystemExit(1)
    if args.probe_only and not result.get('identity_confirmed'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
