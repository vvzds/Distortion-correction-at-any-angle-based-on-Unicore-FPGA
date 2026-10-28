"""Count content changes in a fixed-rate FFmpeg framehash capture."""

import argparse
import collections
from pathlib import Path


def analyze(path: Path, capture_fps: int):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("0,"):
            continue
        fields = [item.strip() for item in line.split(",")]
        if len(fields) != 6:
            raise ValueError(f"Malformed framehash row: {line}")
        rows.append((int(fields[2]), fields[5]))
    if not rows or any(pts != index for index, (pts, _) in enumerate(rows)):
        raise ValueError("Expected a continuous zero-based video PTS sequence")

    changes = [index for index in range(1, len(rows)) if rows[index][1] != rows[index - 1][1]]
    per_second = collections.Counter(index // capture_fps for index in changes)
    runs = []
    previous = 0
    for index in changes + [len(rows)]:
        runs.append(index - previous)
        previous = index
    return {
        "captured_frames": len(rows),
        "duration_s": len(rows) / capture_fps,
        "different_frame_transitions": len(changes),
        "transitions_per_s": len(changes) * capture_fps / len(rows),
        "per_second": [per_second[i] for i in range((len(rows) + capture_fps - 1) // capture_fps)],
        "repeat_run_lengths": dict(sorted(collections.Counter(runs).items())),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("framehash", type=Path)
    parser.add_argument("--capture-fps", type=int, default=30)
    args = parser.parse_args()
    result = analyze(args.framehash, args.capture_fps)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
