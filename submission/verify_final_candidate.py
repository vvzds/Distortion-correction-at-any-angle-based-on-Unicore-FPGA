"""Read-only integrity audit for the 2026-11-04 Gamma/KEY4 candidate."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
if os.name == 'nt' and not str(ROOT).startswith('\\\\?\\'):
    ROOT = Path('\\\\?\\' + str(ROOT))
MANIFEST = json.loads((ROOT / 'submission/final_candidate_manifest.json').read_text(encoding='utf-8'))


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def safe_relative(name):
    normalized = name.replace('\\', '/')
    return (not normalized.startswith('/') and not re.match(r'^[A-Za-z]:', normalized)
            and all(part not in ('', '..') for part in normalized.split('/')))


def main():
    project = ROOT / MANIFEST['project_root']
    archive = ROOT / MANIFEST['source_archive']
    errors = []
    warnings = []

    if not archive.is_file() or sha256_file(archive) != MANIFEST['source_archive_sha256']:
        errors.append('Source archive missing or SHA256 mismatch')

    sums = {}
    sums_path = project / MANIFEST['project_manifest']
    for line in sums_path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'([0-9a-fA-F]{64})\s+[* ]?(.+)', line)
        if not match:
            errors.append('Malformed SHA256SUMS entry: ' + line)
            continue
        expected, name = match.groups()
        name = name.replace('\\', '/')
        if not safe_relative(name) or name in sums:
            errors.append('Unsafe or duplicate manifest path: ' + name)
            continue
        sums[name] = expected.lower()

    checked = 0
    for name, expected in sums.items():
        path = project / name
        if not path.is_file():
            errors.append('Missing project file: ' + name)
        elif sha256_file(path) != expected:
            errors.append('Project SHA256 mismatch: ' + name)
        checked += 1
    if checked != MANIFEST['project_manifest_entries']:
        errors.append(f"Manifest entries {checked} != {MANIFEST['project_manifest_entries']}")

    archive_files = set()
    if archive.is_file():
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace('\\', '/')
                if not safe_relative(name):
                    errors.append('Unsafe ZIP path: ' + info.filename)
                    continue
                prefix = 'pango_quality_function_keys_gamma_highlight_key4_pkg676_20261104/'
                if not name.startswith(prefix):
                    errors.append('Unexpected ZIP root: ' + name)
                    continue
                relative = name[len(prefix):]
                archive_files.add(relative)
                if relative == MANIFEST['project_manifest']:
                    continue
                if relative not in sums:
                    errors.append('Unmanifested ZIP project file: ' + relative)
                elif sha256_bytes(bundle.read(info)) != sums[relative]:
                    errors.append('ZIP/project SHA256 mismatch: ' + relative)
            expected_zip_files = set(sums) | {MANIFEST['project_manifest']}
            if archive_files != expected_zip_files:
                errors.append('ZIP file set differs from project manifest')

    pds_path = project / MANIFEST['project_file']
    pds_text = pds_path.read_text(encoding='utf-8')
    references = set(re.findall(r'\(_(?:file|ip|ip_source_item)\s+"([^"\n]+)"', pds_text))
    inputs = sorted(name for name in references
                    if name.startswith(('source/', 'ipcore/')) or name.endswith('.fdc'))
    for name in inputs:
        if not (project / name).is_file():
            errors.append('Missing PDS input: ' + name)
    if len(inputs) != MANIFEST['pds_input_references']:
        errors.append(f"PDS input references {len(inputs)} != {MANIFEST['pds_input_references']}")

    bitstream = project / MANIFEST['candidate_bitstream']
    if not bitstream.is_file() or sha256_file(bitstream) != MANIFEST['candidate_bitstream_sha256']:
        errors.append('Candidate bitstream missing or SHA256 mismatch')

    source_hash_file = project / 'pds_evidence/key4_direct_display_seed1_source_hashes_20261104.json'
    build_hashes = json.loads(source_hash_file.read_text(encoding='utf-8'))
    mismatches = []
    for name, expected in build_hashes.items():
        path = project / name
        if not path.is_file() or sha256_file(path) != expected.lower():
            mismatches.append(name)
    if mismatches:
        warnings.append('PDS route source hash differs for: ' + ', '.join(mismatches))

    receipt = json.loads((project / 'pds_evidence/key4_direct_display_seed1_receipt_20261104.json').read_text(encoding='utf-8'))
    route_report = project / 'pds_evidence/key4_direct_display_seed1_timing_20261104.rtr'
    report_met = route_report.is_file() and 'Design Summary : All Constraints Met.' in route_report.read_text(encoding='utf-8', errors='replace')

    result = {
        'package_integrity_passed': not errors,
        'archive_sha256': sha256_file(archive) if archive.is_file() else None,
        'archive_files_checked': len(archive_files),
        'manifest_files_checked': checked,
        'pds_input_references': len(inputs),
        'candidate_bitstream_sha256': sha256_file(bitstream) if bitstream.is_file() else None,
        'saved_route_receipt_exit_code': receipt.get('exit_code'),
        'saved_route_receipt_timing_passed': receipt.get('timing_passed'),
        'saved_route_report_all_constraints_met': report_met,
        'saved_route_source_matches_project': not mismatches,
        'saved_route_source_mismatch_files': mismatches,
        'fresh_rebuild_status': MANIFEST['qualification']['fresh_rebuild_status'],
        'fresh_build_source_manifest_sha256': MANIFEST['qualification']['fresh_build_source_manifest_sha256'],
        'fresh_build_completed': False,
        'board_tested': False,
        'errors': errors,
        'warnings': warnings,
        'hardware_accessed': False,
        'simulation_rerun': False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
