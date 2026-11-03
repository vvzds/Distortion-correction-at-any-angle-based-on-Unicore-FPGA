"""Read-only integrity checks for the selected competition project; stdlib only."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    root = Path(__file__).resolve().parents[1]
    if os.name == 'nt' and not str(root).startswith('\\\\?\\'):
        root = Path('\\\\?\\' + str(root))
    selected = json.loads((root/'submission/manifest.json').read_text(encoding='utf-8'))
    project = (root/selected['project_root']).resolve()
    errors = []
    checked = 0
    for line in (project/selected['original_manifest']).read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():
            continue
        expected, name = line.split(None, 1)
        item = (project/name.strip().replace('\\', '/')).resolve()
        if not item.is_relative_to(project):
            errors.append('Manifest path escapes project: ' + name)
            continue
        if not item.is_file():
            errors.append('Missing manifest file: ' + name)
        elif sha256(item) != expected.lower():
            errors.append('SHA256 mismatch: ' + name)
        checked += 1
    if checked != selected['original_manifest_count']:
        errors.append(f"Manifest count {checked} != {selected['original_manifest_count']}")

    bitstream = project/selected['bitstream']
    if not bitstream.is_file() or sha256(bitstream) != selected['bitstream_sha256']:
        errors.append('Recommended bitstream mismatch')
    # The optional original ZIP is omitted from the unpacked competition bundle.
    archive = project/selected['original_project_zip']
    if archive.exists() and sha256(archive) != selected['original_project_zip_sha256']:
        errors.append('Original project ZIP mismatch')

    pds = (project/selected['project_file']).read_text(encoding='utf-8')
    names = set(re.findall(r'\(_(?:file|ip|ip_source_item)\s+"([^"\n]+)"', pds))
    inputs = sorted(name for name in names if name.startswith(('source/', 'ipcore/'))
                    or name.endswith('.fdc'))
    for name in inputs:
        if not (project/name).is_file():
            errors.append('Missing PDS source/IP/constraint: ' + name)
    if not inputs:
        errors.append('No PDS input references discovered')

    summary = json.loads((project/'reports/verification_summary.json').read_text(encoding='utf-8'))
    runs = summary['simulation_runs']
    if not summary['passed'] or len(runs) != selected['qualification']['software_simulation_runs']:
        errors.append('Saved simulation suite has unexpected status/count')
    for name, expected in summary['inputs_sha256'].items():
        path = project/name
        if not path.is_file() or sha256(path) != expected.lower():
            errors.append('Saved suite input differs: ' + name)
    for name in runs:
        path = project/name/'receipt.json'
        if not path.is_file() or not json.loads(path.read_text(encoding='utf-8'))['passed']:
            errors.append('Saved simulation receipt missing/not passed: ' + name)

    board = json.loads((root/selected['evidence']['board']).read_text(encoding='utf-8'))
    if board['programming']['sha256'].lower() != selected['bitstream_sha256']:
        errors.append('Board-tested bitstream does not match selection')
    if not board['programming']['programmed']:
        errors.append('Board receipt has no successful download')
    result = dict(passed=not errors, manifest_files_checked=checked,
                  pds_input_references=len(inputs), saved_simulation_runs=len(runs),
                  bitstream_sha256=selected['bitstream_sha256'], errors=errors,
                  hardware_accessed=False, simulations_rerun=False,
                  original_zip_present=archive.is_file())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
