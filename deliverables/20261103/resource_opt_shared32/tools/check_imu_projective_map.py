"""Fixed-point vectors and ModelSim test for BNO085-driven projective mapping."""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from run_sim import run


def q14(degrees, axis):
    half = math.radians(degrees) / 2
    q = [0, 0, 0, round(math.cos(half) * (1 << 14))]
    q[axis] = round(math.sin(half) * (1 << 14))
    return q


def s32(value):
    value &= 0xffffffff
    return value - (1 << 32) if value & (1 << 31) else value


def rtl_map(current, reference, base):
    x, y, z, w = current
    rx, ry, rz, rw = reference
    dq = [w*rx-x*rw-y*rz+z*ry,
          w*ry-x*rz-y*rw+z*rx,
          w*rz-x*ry+y*rx-z*rw,
          w*rw+x*rx+y*ry+z*rz]
    dx, dy, dz, dw = [s32(v) >> 14 for v in dq]
    xx, yy, zz, ww = dx*dx, dy*dy, dz*dz, dw*dw
    xy, xz, yz, xw, yw, zw = dx*dy, dx*dz, dy*dz, dx*dw, dy*dw, dz*dw
    one = 1 << 28
    s00, s01, s02 = one-2*(yy+zz), 2*(xy-zw), 2*(xz+yw)
    s10, s11, s12 = 2*(xy+zw), one-2*(xx+zz), 2*(yz-xw)
    s20, s21, s22 = 2*(xz-yw), 2*(yz+xw), one-2*(xx+yy)
    # camera_from_sensor = [[0,-1,0],[0,0,-1],[1,0,0]]
    r = [[s11, s12, -s10], [s21, s22, -s20], [-s01, -s02, s00]]
    b = [base[i] for i in range(6)]
    nums = [r[0][0]*b[0]+r[0][1]*b[3],
            r[0][0]*b[1]+r[0][1]*b[4],
            r[0][0]*b[2]+r[0][1]*b[5]+(r[0][2] << 20),
            r[1][0]*b[0]+r[1][1]*b[3],
            r[1][0]*b[1]+r[1][1]*b[4],
            r[1][0]*b[2]+r[1][1]*b[5]+(r[1][2] << 20),
            r[2][0] << 14, r[2][1] << 14]
    den = r[2][2]
    if den < (1 << 27):
        raise ValueError('Test pose makes denominator invalid')
    # Verilog unsigned long division on magnitudes truncates toward zero.
    out = [(-(abs(n)//den) if n < 0 else abs(n)//den) for n in nums]
    return [s32(n) for n in out]


def main():
    build = ROOT / 'build' / 'vectors'
    build.mkdir(parents=True, exist_ok=True)
    # Production startup affine calibration, packed exactly as host/model.py.
    base = [178042, 0, -614476, 0, 178078, -395589]
    # Cases: capture neutral, rotate about each sensor axis, then recapture.
    poses = [(1, q14(0, 0)), (0, q14(12, 2)),
             (0, q14(-9, 1)), (1, q14(21, 0))]
    vectors = build / 'imu_projective_map.txt'
    config = build / 'imu_projective_map_config.hex'
    words = base + [98809312, 98789197, 57903224, 37269520,
                    -1600054, 657241, -1271, -465, 1, 0]
    config.write_text(''.join(f'{v & 0xffffffff:08x}\n' for v in words), encoding='ascii')
    reference = None
    rows = []
    for capture, pose in poses:
        if capture:
            reference = pose
        expected = rtl_map(pose, reference, base)
        rows.append(f"{capture} {pose[0]} {pose[1]} {pose[2]} {pose[3]} " +
                    ' '.join(f'{v & 0xffffffff:08x}' for v in expected) + '\n')
    vectors.write_text(''.join(rows), encoding='ascii')
    folder = run('imu_projective_map_tb',
                 ['source/rtl/mul32_pipe.v', 'source/rtl/imu_projective_map.v', 'sim/imu_projective_map_tb.v'],
                 ['+CONFIG=build/vectors/' + config.name,
                  '+VECTORS=build/vectors/' + vectors.name,
                  '+RESULT=build/vectors/imu_projective_map_actual.txt'])
    expected_rows = [line.split() for line in vectors.read_text(encoding='ascii').splitlines()]
    actual_rows = [line.split() for line in
                   (build / 'imu_projective_map_actual.txt').read_text(encoding='ascii').splitlines()]
    if len(actual_rows) != len(expected_rows):
        raise SystemExit(f'Expected {len(expected_rows)} hardware results; got {len(actual_rows)}')
    for index, (expected, actual) in enumerate(zip(expected_rows, actual_rows)):
        expected_coeffs = [int(value, 16) for value in expected[5:11]] + [
            int(expected[11], 16) & 0xffff, int(expected[12], 16) & 0xffff]
        actual_coeffs = [int(value, 16) for value in actual[1:]]
        if int(actual[0]) != index or actual_coeffs != expected_coeffs:
            raise SystemExit(f'Exact coefficient mismatch in pose {index}: '
                             f'actual={actual_coeffs!r}, expected={expected_coeffs!r}')
    print(f'PASS exact IMU projective map: {len(poses)} reference/pose cases; evidence: {folder}')


if __name__ == '__main__':
    main()
