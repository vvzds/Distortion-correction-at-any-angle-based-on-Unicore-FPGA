"""Package the resource-optimized project, bitstreams, and evidence together."""
from pathlib import Path
import hashlib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "deliverables" / "20261103" / "resource_opt_shared32"
ARCHIVE = DELIVERY / "pango_quality_function_keys_resource_opt_full_20261103.zip"
EXCLUDED = {
    ARCHIVE.name,
    ARCHIVE.name + ".sha256",
    "pango_quality_function_keys_resource_opt_20261103.zip",
    "pango_quality_function_keys_resource_opt_20261103.zip.sha256",
    "SHA256SUMS.txt",
}


def main() -> None:
    with zipfile.ZipFile(ARCHIVE, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for path in sorted(DELIVERY.rglob("*")):
            if path.is_file() and path.name not in EXCLUDED:
                output.write(path, Path("resource_opt_shared32") / path.relative_to(DELIVERY))
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    ARCHIVE.with_suffix(ARCHIVE.suffix + ".sha256").write_text(
        f"{digest}  {ARCHIVE.name}\n", encoding="ascii"
    )
    print(f"archive={ARCHIVE}")
    print(f"bytes={ARCHIVE.stat().st_size}")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
