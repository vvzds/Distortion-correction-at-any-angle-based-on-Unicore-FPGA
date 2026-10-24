"""Archive the design review; G4 implementation remains explicitly gated."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(r"C:/Users/叶翔/xwechat_files/wxid_qanrp2aqlq8h22_bb90/msg/file/2026-10/G4_读地址拆级方案_评审意见_设计方_20261018(1).md")


def main():
    data = SOURCE.read_bytes()
    dest = ROOT / "verification/design_g4_review_20261018/G4_读地址拆级方案_评审意见_设计方_20261018.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest().upper()
    text = data.decode("utf-8-sig")
    assert "方案评审通过" in text
    assert "不构成启动批准" in text
    assert "A+B 并行" in text
    receipt = {
        "source": str(SOURCE),
        "archived_path": dest.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": digest,
        "review_status": "方案评审通过",
        "implementation_approval": False,
        "decision_options": {"A": "start G4", "B": "corr_top P&R first", "C": "parallel"},
        "production_rtl_changed": False,
    }
    (ROOT / "verification/g4_review_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
