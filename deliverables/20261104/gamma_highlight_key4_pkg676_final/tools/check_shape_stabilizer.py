"""Geometry/noisy-fit regression for shape breathing; does not open devices."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'host'))
from model import affine
from stabilizer import ShapeStabilizer, homogeneous


def main():
    base = homogeneous(affine(zoom=1.15))
    quality = dict(coverage=.55, cells=10, inliers=120, inlier_ratio=.9, rms_px=1.)
    regulator = ShapeStabilizer(base)
    raw, applied = [], []
    previous = np.zeros(2)
    max_rate = 0.
    center = np.array([959.5, 539.5, 1.])
    # Rotate while scale/shear estimates alternate like the observed bad fits.
    for i in range(240):
        motion = homogeneous(affine(i*.2, 1., 15., -7.))
        shape = np.eye(3)
        shape[:2, :2] = [[1.10 if (i//15)%2 else .96, .025], [0, .89 if (i//15)%2 else 1.02]]
        target = motion@shape@base
        result, diagnostics = regulator.constrain(target, quality, 1/30)
        raw.append(np.linalg.svd((target@np.linalg.inv(base))[:2,:2], compute_uv=False))
        applied.append(np.linalg.svd((result@np.linalg.inv(base))[:2,:2], compute_uv=False))
        values = np.linalg.eigvalsh(regulator.log_stretch)
        max_rate = max(max_rate, np.max(np.abs(values-previous))*30)
        previous = values
        assert np.linalg.norm((target@center-result@center)[:2]) < 1e-9
    applied = np.array(applied)
    assert applied.max() <= 1.02+1e-9 and applied.min() >= 1/1.02-1e-9
    assert max_rate <= .015+1e-9
    # Narrow matches must not introduce stretch even with a low fit residual.
    regulator = ShapeStabilizer(base)
    narrow = dict(quality, coverage=.15, cells=5)
    for _ in range(90):
        result, diag = regulator.constrain(target, narrow, 1/30)
        assert not diag['supported']
        assert np.allclose(np.linalg.svd((result@np.linalg.inv(base))[:2,:2],compute_uv=False),1.)
    # Genuine small sustained affine pitch/stretch remains possible.
    regulator = ShapeStabilizer(base)
    pitch = np.eye(3); pitch[1,1] = .985; pitch[1,2] = 8.
    for _ in range(120):
        result, _ = regulator.constrain(pitch@base, quality, 1/30)
    assert .985 < (result@np.linalg.inv(base))[1,1] < .991
    # Rigid mode preserves roll and center, including full roll angles.
    regulator = ShapeStabilizer(base, limit=0.)
    for angle in range(0,360,15):
        target = homogeneous(affine(angle))@base
        result, _ = regulator.constrain(target, quality, 1/30)
        assert np.max(np.abs(target-result)) < 1e-9
    report = dict(passed=True, hardware_opened=False,
        checks=['Noisy stretch stays within 2% and log-rate 1.5%/s',
                'Narrow feature support cannot change shape',
                'Sustained small pitch stretch remains supported',
                'Full-roll and center displacement preserved'],
        raw_max_axis_ratio=float(max(s[0]/s[1] for s in raw)),
        constrained_max_axis_ratio=float(np.max(applied[:,0]/applied[:,1])),
        max_log_stretch_rate=max_rate)
    (ROOT/'reports/shape_stabilizer_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
