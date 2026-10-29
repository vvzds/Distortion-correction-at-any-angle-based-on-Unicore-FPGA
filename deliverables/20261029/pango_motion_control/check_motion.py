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
    connection.sequence = 39
    connection.serial = FakeSerial()
    connection._known_config_sequences = None
    status_queries = [0]
    def initial_status():
        status_queries[0] += 1
        connection.next_sequence()
        connection._known_config_sequences = (1, 2)
        return {'active_sequence': 1, 'pending_sequence': 2}
    connection.status = initial_status
    def query_samples():
        base = connection.serial.written_at
        samples = [
            ({'active_sequence': 1, 'pending_sequence': 2,
              'core_fault': False, 'write_fault': False}, base + .001, base + .003),
            ({'active_sequence': 41, 'pending_sequence': 41,
              'core_fault': False, 'write_fault': False}, base + .023, base + .025),
        ]
        for result, sent, received in samples:
            connection.sequence = (connection.sequence + 1) & 0xffff
            connection._known_config_sequences = (result['active_sequence'],
                                                   result['pending_sequence'])
            yield result, sent, received
    query_samples = query_samples()
    connection.status_timed = lambda: next(query_samples)
    status, sent_at, active_estimate_at = connection.configure_timed([0] * 16)
    assert status['active_sequence'] == 41
    assert math.isclose(active_estimate_at - sent_at, .013, abs_tol=.002)
    assert status_queries[0] == 1
    def next_activation():
        base = connection.serial.written_at
        result = {'active_sequence': 44, 'pending_sequence': 44,
                  'core_fault': False, 'write_fault': False}
        connection.sequence = (connection.sequence + 1) & 0xffff
        connection._known_config_sequences = (44, 44)
        return result, base + .001, base + .003
    connection.status_timed = next_activation
    status,_,_=connection.configure_timed([0]*16,poll_interval=.005)
    assert status['active_sequence'] == 44 and status_queries[0] == 1
    print('PASS midpoint activation estimate, 5 ms poll option, and cached sequence reuse')

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
