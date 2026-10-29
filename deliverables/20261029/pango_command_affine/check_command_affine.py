"""Offline command controller checks; fake UART, no camera or board access."""
import math
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'host'))

from command_affine import AffineCommander, Pose, advance_pose
from model import compile_registers, load_calibration, preflight


class FakeLink:
    def __init__(self):
        self.packets = []
        self.closed = False
        self.frames = 100

    def frame_state(self):
        return {'frames': self.frames, 'version': 0x00020001}

    def configure(self, registers, timeout):
        self.packets.append(('exact', registers))
        return self.status()

    def set_target(self, registers):
        self.packets.append(('target', registers))

    def status(self):
        self.frames += 1
        return {'frames': self.frames, 'core_fault': False, 'write_fault': False,
                'overflow_tiles': 0, 'rx_errors': 0}

    def close(self):
        self.closed = True


def main():
    calibration = load_calibration()
    start = Pose()
    target = Pose(angle=270.)
    slow = advance_pose(start, target, 1/30, angular_speed=45)
    fast = advance_pose(start, target, 1/30, angular_speed=540)
    assert math.isclose(slow.angle, 1.5)
    assert math.isclose(fast.angle, 18.)
    assert fast.angle > slow.angle > 0
    assert advance_pose(Pose(angle=179), Pose(angle=181), 1/30, 540).angle == 181
    assert advance_pose(Pose(angle=179), Pose(angle=-179), 1/30, 540).angle == 161
    profiles = []
    for angle in (-270, -180, -90, -.1, 0, .1, 90, 180, 270, 360):
        for shear in (0., .1, -.1):
            pose = Pose(angle=angle, shear=shear)
            pose.validate()
            report = preflight(calibration, pose.matrix()[:2], False)[1]
            assert report['valid_fraction'] > .98, (angle, shear, report['valid_fraction'])
            assert report['max_patch_width'] <= 256
            assert report['max_patch_height'] <= 256
            profiles.append(dict(angle=angle, shear=shear, **report))

    link = FakeLink()
    commander = AffineCommander(link, calibration, angular_speed=540)
    commander.start()
    commander.set_target(Pose(angle=270.))
    deadline = time.monotonic()+1.
    while commander.snapshot()['commands_sent'] < 2 and time.monotonic() < deadline:
        time.sleep(.005)
    before = commander.snapshot()
    assert 0 < before['current'].angle < 270
    assert before['commands_sent'] >= 2
    commander.set_target(Pose(angle=-90.))
    deadline = time.monotonic()+1.
    while commander.snapshot()['current'].angle >= before['current'].angle and time.monotonic() < deadline:
        time.sleep(.005)
    after = commander.snapshot()
    assert after['target'].angle == -90
    assert after['current'].angle < before['current'].angle
    assert after['error'] is None
    commander.close()
    assert link.closed
    assert link.packets[-1] == ('exact', compile_registers(calibration,
                                                          Pose(angle=0, zoom=1).matrix()[:2], False))
    assert all(regs[15] == 0 for kind, regs in link.packets if kind == 'target')
    for bad in (Pose(angle=float('nan')), Pose(shear=.6), Pose(zoom=.4)):
        try:
            bad.validate()
        except ValueError:
            pass
        else:
            raise AssertionError(f'Unsafe pose accepted: {bad}')
    class OldFirmware(FakeLink):
        def frame_state(self):
            raise ValueError('Clean smooth firmware required')
    old = OldFirmware()
    try:
        AffineCommander(old, calibration).start()
    except ValueError:
        pass
    else:
        raise AssertionError('Old firmware accepted')
    assert not old.packets
    class FaultLink(FakeLink):
        def status(self):
            result = super().status()
            result['core_fault'] = self.frames > 101
            return result
    fault = FaultLink()
    fault_controller = AffineCommander(fault, calibration)
    fault_controller.start()
    fault_controller.set_target(Pose(angle=10))
    deadline = time.monotonic()+1.
    while fault_controller.snapshot()['error'] is None and time.monotonic() < deadline:
        time.sleep(.005)
    assert fault_controller.snapshot()['error'] is not None
    fault_controller.close()
    assert fault.closed
    receipt = {'passed': True, 'hardware_opened': False,
               'scenarios': len(profiles),
               'min_valid_fraction': min(p['valid_fraction'] for p in profiles),
               'max_patch_width': max(p['max_patch_width'] for p in profiles),
               'max_patch_height': max(p['max_patch_height'] for p in profiles),
               'slow_deg_per_frame': slow.angle,
               'fast_deg_per_frame': fast.angle,
               'target_updates_sent': len([1 for kind, _ in link.packets if kind == 'target'])}
    (ROOT/'reports/command_affine_check.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8')
    print('PASS full-angle fixed-crop preflight, slow/fast slew, newest-target UART, fault stop, exact restore')


if __name__ == '__main__':
    main()
