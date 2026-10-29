"""Read newline-delimited JSON target poses from stdin and drive the FPGA."""
import argparse
import json
import sys

from command_affine import AffineCommander, Pose
from model import ROOT, load_calibration
from protocol import Connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', default='COM9')
    parser.add_argument('--calibration', default=str(ROOT/'calibration/ov5640_1080p.json'))
    parser.add_argument('--speed', choices=('slow', 'normal', 'fast'), default='normal')
    parser.add_argument('--smooth', action='store_true',
                        help='Enable extra FPGA half-distance smoothing per frame')
    args = parser.parse_args()
    speed = dict(slow=(45., 300., .25, .4), normal=(180., 900., .7, 1.),
                 fast=(540., 1800., 1.5, 2.))[args.speed]
    link = Connection(args.port)
    controller = AffineCommander(link, load_calibration(args.calibration),
                                 angular_speed=speed[0], pixel_speed=speed[1],
                                 shear_speed=speed[2], zoom_speed=speed[3],
                                 smooth=args.smooth)
    try:
        controller.start()
        print(json.dumps({'ready': True, 'firmware': 'clean_smooth_v2'}), flush=True)
        for line in sys.stdin:
            if controller.snapshot()['error']:
                raise RuntimeError(controller.snapshot()['error'])
            try:
                data = json.loads(line)
                if not isinstance(data, dict):
                    raise ValueError('JSON object expected')
                if data.get('command') == 'status':
                    state = controller.snapshot()
                    print(json.dumps({'current': state['current'].__dict__,
                                      'target': state['target'].__dict__,
                                      'frames': state['frames'],
                                      'commands_sent': state['commands_sent']}), flush=True)
                    continue
                if data.get('command') == 'reset':
                    pose = Pose()
                else:
                    current = controller.snapshot()['target'].__dict__.copy()
                    current.update(data)
                    pose = Pose(**current)
                controller.set_target(pose)
                print(json.dumps({'accepted': pose.__dict__}), flush=True)
            except (ValueError, TypeError) as exc:
                print(json.dumps({'error': str(exc)}), flush=True)
    finally:
        controller.close()


if __name__ == '__main__':
    main()
