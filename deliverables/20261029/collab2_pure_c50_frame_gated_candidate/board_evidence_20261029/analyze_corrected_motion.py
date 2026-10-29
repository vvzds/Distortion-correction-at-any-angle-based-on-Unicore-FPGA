"""Measure content changes in a nominal 30 fps corrected HDMI recording."""

import argparse
from collections import Counter

import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    capture = cv2.VideoCapture(args.video)
    if not capture.isOpened():
        raise SystemExit("Cannot open capture")
    fps = capture.get(cv2.CAP_PROP_FPS)
    previous = None
    means = []
    changed = Counter()
    frames = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        gray = cv2.cvtColor(cv2.resize(frame, (320, 180)), cv2.COLOR_BGR2GRAY)
        clean = cv2.medianBlur(gray, 3)
        if previous is not None:
            mad = np.abs(clean.astype(np.int16) - previous.astype(np.int16)).mean()
            means.append(float(mad))
            if mad > args.threshold:
                changed[frames // 30] += 1
        previous = clean
        frames += 1
    capture.release()
    if not means:
        raise SystemExit("Insufficient frames")
    full_seconds = frames // 30
    print(f"frames={frames} nominal_fps={fps:.6f} duration_s={frames / fps:.3f}")
    print("denoised_mad_percentiles=" + ",".join(
        f"p{p}:{np.percentile(means, p):.3f}" for p in (0, 10, 25, 50, 75, 90, 99, 100)
    ))
    print(f"threshold={args.threshold} transitions={sum(changed.values())}")
    print(f"complete_seconds={full_seconds} per_second={[changed[i] for i in range(full_seconds)]}")


if __name__ == "__main__":
    main()
