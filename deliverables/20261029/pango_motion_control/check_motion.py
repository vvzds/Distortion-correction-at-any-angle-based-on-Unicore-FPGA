"""Deterministic checks for predictive affine-motion timing."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'host'))
from motion import (motion_pose, trajectory_samples, update_latency_estimate,
                    verify_trajectory)
from protocol import Connection


def main():
    period = 6.0
    first = motion_pose(0, 0, 45, 0, .1, period)
    quarter = motion_pose(period / 4, 0, 45, 0, .1, period)
    half = motion_pose(period / 2, 0, 45, 0, .1, period)
    assert first == (0.0, .1)
    assert math.isclose(quarter[0], 45.0, abs_tol=1e-12)
    assert math.isclose(half[0], 0.0, abs_tol=1e-12)
    assert math.isclose(motion_pose(0, 0, 45, 0, .1, period, 250)[0],
                        motion_pose(.25, 0, 45, 0, .1, period)[0], abs_tol=1e-12)
    samples = trajectory_samples(10, 180, 0, .2)
    angles = [angle for angle, _ in samples]
    assert len(samples) == 360
    assert min(angles) <= -169.9 and max(angles) >= 189.9
    assert update_latency_estimate(None, 50) == 50
    assert math.isclose(update_latency_estimate(50, 100), 60)
    print('PASS predictive phase, smooth cycle extrema, full-angle trajectory, and latency EMA')

    class FakeSerial:
        def write(self, data):
            self.data = data
            self.written_at = __import__('time').monotonic()

    connection = object.__new__(Connection)
    connection.sequence = 40
    connection.serial = FakeSerial()
    connection.status = lambda: {'active_sequence': 1, 'pending_sequence': 2}
    def query_samples():
        base = connection.serial.written_at
        yield ({'active_sequence': 1, 'core_fault': False, 'write_fault': False},
               base + .001, base + .003)
        yield ({'active_sequence': 41, 'core_fault': False, 'write_fault': False},
               base + .023, base + .025)
    query_samples = query_samples()
    connection.status_timed = lambda: next(query_samples)
    status, sent_at, active_estimate_at = connection.configure_timed([0] * 16)
    assert status['active_sequence'] == 41
    assert math.isclose(active_estimate_at - sent_at, .013, abs_tol=.002)
    print('PASS UART activation time uses the midpoint between old/new sequence observations')

    from model import load_calibration
    report = verify_trajectory(load_calibration(), 0, 45, 1, 0, 0, 0,
                               .1, True, False)
    assert report['samples'] >= 72
    assert report['min_valid_fraction'] == 1.0
    assert report['max_patch_width'] <= 192
    assert report['max_patch_height'] <= 192
    print('PASS default 45-degree rotation and tilt path preflight:', report)


if __name__ == '__main__':
    main()
