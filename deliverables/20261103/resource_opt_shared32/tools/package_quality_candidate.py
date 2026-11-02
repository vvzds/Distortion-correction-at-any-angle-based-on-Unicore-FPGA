"""Create a shareable full project archive without volatile PDS databases."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OMIT_DIRS = {"build", ".git", ".venv", "__pycache__"}
OMIT_SUFFIXES = {".pyc", ".pyo"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT.parent / "pango_bno085_quality_denoise_sharpen_osd_20261103.zip",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    root_name = ROOT.name
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() in OMIT_SUFFIXES:
            continue
        relative = path.relative_to(ROOT)
        if any(part in OMIT_DIRS for part in relative.parts):
            continue
        if path.resolve() == output:
            continue
        files.append((path, Path(root_name) / relative))

    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for path, archive_name in sorted(files, key=lambda item: item[1].as_posix()):
            archive.write(path, archive_name.as_posix())

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(f"archive={output}")
    print(f"files={len(files)}")
    print(f"bytes={output.stat().st_size}")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
