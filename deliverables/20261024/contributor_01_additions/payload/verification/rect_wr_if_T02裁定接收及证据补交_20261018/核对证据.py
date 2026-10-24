"""日志内容/换行哈希、独立整数恢复预算检查；非RTL仿真。"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = "321e85c1ffde2c2cd5abdd3b5ed260e5bf7e2ea6eb374fc96f550fdea9e61ca1"


def main():
    raw = (ROOT / "received/W0_W8_vsim.log").read_bytes()
    canonical = (ROOT / "verification/modelsim/W0_W8_vsim.log").read_bytes()
    assert canonical == raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    assert len(canonical) == 5032 and hashlib.sha256(canonical).hexdigest() == EXPECTED
    log = raw.decode("utf-8-sig")
    lines = [line[2:] if line.startswith("# ") else line for line in log.splitlines()]
    for number in range(9):
        assert any(line.startswith("[W{}] PASS (err=0)".format(number)) for line in lines)
    assert "=== ALL TESTS PASSED (err=0) ===" in lines
    assert "quit -force -code 0" in lines
    assert "seed_up=49a2137b seed_slot=c0213471 seed_wr=17009bc3" in log
    # examine值必须紧随对应命令，不能只凭整份日志包含0/1/4推定。
    for command, value in (
        ("set failures [examine -radix decimal /rect_wr_if_tb/err]", "0"),
        ("set completed_normally [examine -radix unsigned /rect_wr_if_tb/tb_done]", "1"),
        ("set completed [examine -radix decimal /rect_wr_if_tb/commits]", "4"),
    ):
        assert lines[lines.index(command) + 1] == value
    icarus = (ROOT / "received/ALL_icarus_baseline.log").read_text(encoding="utf-8-sig")
    # $finish的工具自带路径/时间提示格式不同，TB本身每一行输出逐字比对。
    tb_lines = [line for line in icarus.splitlines() if line.strip() and "$finish called at" not in line]
    assert all(line in lines for line in tb_lines)

    recovery = []
    for gap in (3, 4):
        pixels = 3976  # ceil(pixels/2)=1988，已受理字数起算0
        accepted = 0
        snapshots = {}
        reached = None
        for elapsed in range(1, 3729):
            pixels += 1
            # 恢复第1拍先受理帧尾字，随后发生换帧固有拍，其余连续受理。
            if not 2 <= elapsed <= gap + 1:
                accepted += 1
            wm = (pixels + 1) // 2 - accepted
            if elapsed in (3724, 3726, 3728):
                snapshots[str(elapsed)] = wm
            if reached is None and wm <= 128:
                reached = elapsed
        assert reached == 3720 + 2 * gap
        assert snapshots["3724"] == 126 + gap
        recovery.append({"gap_cycles": gap, "wm_snapshots": snapshots,
                         "first_elapsed_wm_le_128": reached,
                         "accepted_cycles_required": reached - gap})
    report = {
        "received_bytes": len(raw), "received_sha256": hashlib.sha256(raw).hexdigest(),
        "crlf_restored_bytes": len(canonical), "crlf_restored_sha256": EXPECTED,
        "W0_W8_PASS_and_verdict_readouts": True,
        "icarus_all_TB_output_lines_found_in_modelsim_log": True,
        "icarus_TB_lines_compared": len(tb_lines),
        "excluded_simulator_specific_line": "$finish called at ... (Icarus path/time diagnostic)",
        "locally_ran_modelsim": False,
        "integer_budget_model_only": True, "recovery": recovery,
    }
    (ROOT / "核对结果.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
