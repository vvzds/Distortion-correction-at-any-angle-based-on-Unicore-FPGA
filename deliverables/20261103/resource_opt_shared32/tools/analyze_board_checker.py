"""Measure checker-grid straightness in paired real-board captures.

Frames must be PNGs decoded from the capture card. This reports image-domain
straightness only; it is not an MTF50 or ISO12233 certification.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from check_real_images import straightness


def detect(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.threshold(gray, 20, 255, cv2.THRESH_BINARY)[1]
    ok, corners = cv2.findChessboardCornersSB(
        binary, (11, 8), cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok:
        raise ValueError('Could not detect all 88 checker intersections')
    return corners.reshape(8, 11, 2).astype(float)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture_directory', type=Path)
    args = parser.parse_args()
    report = dict(method='11x8 checker corners from gray-threshold-20 PNG; total least squares perpendicular residual',
        capture_transport='Hagibis DirectShow MJPG decoded to PNG; not a raw FPGA DDR dump',
        stages=[])
    for stage in ('raw_before', 'corrected', 'raw_return'):
        directory = args.capture_directory / stage
        images = []
        for path in sorted(directory.glob('frame_*.png')):
            image = cv2.imread(str(path))
            if image is None:
                raise ValueError(f'Unreadable capture: {path}')
            corners = detect(image)
            item = dict(file=path.name,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                straightness=straightness(corners))
            images.append(item)
            print(stage, path.name, json.dumps(item['straightness']), flush=True)
        if len(images) != 3:
            raise ValueError(f'Expected three frames for {stage}, got {len(images)}')
        report['stages'].append(dict(name=stage, frames=images,
            median_rms_px=float(np.median([i['straightness']['rms_px'] for i in images]))))
    before, corrected, returned = report['stages']
    report['comparison'] = dict(raw_before_median_rms_px=before['median_rms_px'],
        corrected_median_rms_px=corrected['median_rms_px'],
        raw_return_median_rms_px=returned['median_rms_px'],
        raw_return_delta_px=returned['median_rms_px']-before['median_rms_px'],
        improvement_ratio=before['median_rms_px']/corrected['median_rms_px'])
    target = args.capture_directory / 'straightness_report.json'
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report['comparison'], indent=2))


if __name__ == '__main__':
    main()
