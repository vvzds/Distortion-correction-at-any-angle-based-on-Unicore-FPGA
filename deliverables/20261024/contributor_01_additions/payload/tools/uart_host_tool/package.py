#!/usr/bin/env python3
"""标准库交付打包：自测、语法检查、哈希清单、解压复测。"""

import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parent
DELIVERY_NAME = "uart_host_tool_v1.0_tlimfix_refill_20261018"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_project(root):
    for path in sorted(root.rglob("*.py")):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 8))
    environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        [sys.executable, "-B", str(root / "uart_tool.py"), "selftest"],
        cwd=str(root), env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding="utf-8", timeout=60,
    )
    expected = ["[U{}] PASS".format(number) for number in range(6)]
    if result.returncode or any(line not in result.stdout.splitlines() for line in
                                expected + ["=== ALL TESTS PASSED ==="]):
        raise RuntimeError("自测失败: {}\n{}".format(root, result.stdout))
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-parent", type=Path, default=ROOT.parent)
    args = parser.parse_args()
    parent = args.output_parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    stage = parent / DELIVERY_NAME
    archive = parent / (DELIVERY_NAME + ".zip")
    evidence = parent / (DELIVERY_NAME + "_verification.json")
    checksum = parent / (DELIVERY_NAME + ".zip.sha256")
    for target in (stage, archive, evidence, checksum):
        if target.exists():
            raise FileExistsError("保留已有文件，请换一个 --output-parent: {}".format(target))
    if parent == ROOT or ROOT in parent.parents:
        raise ValueError("输出目录不能位于源码目录内部")

    source_output = check_project(ROOT)
    (ROOT / "verification").mkdir(exist_ok=True)
    (ROOT / "verification" / "selftest_console.log").write_text(source_output, encoding="utf-8")
    shutil.copytree(ROOT, stage, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git"))
    staged_output = check_project(stage)
    if source_output != staged_output:
        raise RuntimeError("源码与交付副本的自测输出不一致")

    files = sorted(path for path in stage.rglob("*") if path.is_file())
    manifest = "".join("{}  {}\n".format(sha256(path), path.relative_to(stage).as_posix())
                       for path in files)
    (stage / "SHA256SUMS.txt").write_text(manifest, encoding="utf-8")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                output.write(path, arcname=path.relative_to(parent).as_posix())

    # 只解压本脚本刚生成的归档，核对完整文件集及每个文件的内容。
    with tempfile.TemporaryDirectory(prefix="uart_delivery_check_", dir=str(parent)) as temporary:
        with zipfile.ZipFile(archive) as source:
            if source.testzip() is not None:
                raise RuntimeError("ZIP CRC 校验失败")
            source.extractall(temporary)
        extracted = Path(temporary) / DELIVERY_NAME
        if (extracted / "SHA256SUMS.txt").read_text(encoding="utf-8") != manifest:
            raise RuntimeError("解压后哈希清单不一致")
        names = {path.relative_to(extracted).as_posix()
                 for path in extracted.rglob("*") if path.is_file()}
        expected_names = {path.relative_to(stage).as_posix() for path in files}
        if names != expected_names | {"SHA256SUMS.txt"}:
            raise RuntimeError("解压后文件集不一致")
        for path in files:
            if sha256(extracted / path.relative_to(stage)) != sha256(path):
                raise RuntimeError("解压后文件哈希不一致: {}".format(path.name))
        extracted_output = check_project(extracted)
        if extracted_output != source_output:
            raise RuntimeError("解压后自测输出不一致")

    archive_hash = sha256(archive)
    checksum.write_text("{}  {}\n".format(archive_hash, archive.name), encoding="utf-8")
    report = {
        "delivery_date": "2026-10-18",
        "python": sys.version,
        "pyserial_installed": importlib.util.find_spec("serial") is not None,
        "hardware_tested": False,
        "archive": archive.name,
        "archive_sha256": archive_hash,
        "payload_file_count": len(files),
        "zip_crc": "PASS", "extracted_file_set_and_sha256": "PASS",
        "python_3_8_grammar_check": "PASS (not a Python 3.8 runtime test)",
        "source_selftest": source_output,
        "staged_selftest": staged_output,
        "extracted_selftest": extracted_output,
    }
    evidence.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(source_output, end="")
    print("文件哈希、ZIP CRC、解压副本自测：PASS")
    print("交付: {}".format(archive))
    print("SHA-256: {}".format(archive_hash))
    return 0


if __name__ == "__main__":
    sys.exit(main())
