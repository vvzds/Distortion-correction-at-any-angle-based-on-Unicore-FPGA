"""Rebuild the locked seed-2 Gamma project in isolation through bitstream."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


ROOT = Path(r"C:\Users\lenovo\Desktop\ww\高阶任务三_仓库审查与启动_20261027")
BASE = ROOT / "physical_seed2"
BUILD = ROOT / "bitstream_seed2_isolated"
EVIDENCE = ROOT / "verification" / "seed2_bitstream_full"
OLD = json.loads((ROOT / "verification" / "timing_physical_seed2" / "receipt.json").read_text(encoding="utf-8"))
PDS = Path(r"D:\FPGA PDS\PDS_2022.2-SP6.1-win64\bin\pds_shell.exe")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(data):
    (EVIDENCE / "receipt.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    assert not BUILD.exists() and not EVIDENCE.exists(), "Inspect an existing run before retrying"
    assert OLD["status"] == "PASS" and sha(PDS) == OLD["tool_sha256"]
    for name, digest in OLD["source_sha256"].items():
        assert sha(BASE / name) == digest, name
    assert sha(BASE / "HDMI_DDR3_OV5640_test.fdc") == OLD["constraint_sha256"]
    assert sha(BASE / "run_physical.tcl") == OLD["script_sha256"]
    for name in ("source", "ipcore"):
        shutil.copytree(BASE / name, BUILD / name)
    shutil.copy2(BASE / "HDMI_DDR3_OV5640_test.fdc", BUILD / "HDMI_DDR3_OV5640_test.fdc")
    script = (BASE / "run_physical.tcl").read_text(encoding="utf-8")
    assert script.count('puts "ADV3_PHASE=FINISHED"') == 1
    script = script.replace('puts "ADV3_PHASE=FINISHED"',
                            'gen_bit_stream\nputs "ADV3_PHASE=BITSTREAM_DONE"\nputs "ADV3_PHASE=FINISHED"')
    (BUILD / "run_full_bitstream.tcl").write_text(script, encoding="utf-8")
    inputs = {name: sha(BUILD / name) for name in OLD["source_sha256"]}
    assert inputs == OLD["source_sha256"]
    EVIDENCE.mkdir()
    drive = next(letter + ":" for letter in "QRSTUVWX" if not Path(letter + ":/").exists())
    subprocess.run(["subst", drive, str(BUILD)], check=True)
    command = [str(PDS), "-file", drive + "/run_full_bitstream.tcl",
               "-work_dir", drive + "/", "-project_name", "advanced3_seed2_gamma"]
    receipt = {"state": "STARTING", "started": datetime.datetime.now().astimezone().isoformat(),
               "command": command, "seed": 2, "source_sha256": inputs,
               "constraint_sha256": OLD["constraint_sha256"], "script_sha256": sha(BUILD / "run_full_bitstream.tcl"),
               "tool_sha256": OLD["tool_sha256"], "timeout_seconds": 5400}
    save(receipt)
    tick = time.monotonic()
    try:
        env = dict(os.environ, PATH=str(PDS.parent) + os.pathsep + os.environ.get("PATH", ""))
        with (EVIDENCE / "console.log").open("wb") as log:
            process = subprocess.Popen(command, cwd=BUILD, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            receipt.update(state="RUNNING", pid=process.pid)
            save(receipt)
            print("FULL_BITSTREAM_RUNNING", process.pid, flush=True)
            while process.poll() is None:
                elapsed = time.monotonic() - tick
                receipt.update(elapsed_seconds=round(elapsed, 1), console_bytes=log.tell())
                save(receipt)
                if elapsed >= receipt["timeout_seconds"]:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    receipt["state"] = "TIMEOUT"
                    break
                time.sleep(10)
            code = process.wait(timeout=60)
        body = (EVIDENCE / "console.log").read_text(errors="replace")
        timing_paths = list(BUILD.rglob("hdmi_ddr_ov5640_top_timing_summary_after_hold_fix.txt"))
        bit_paths = sorted(set(BUILD.rglob("*.sbit")) | set(BUILD.rglob("*.bit")))
        outputs = [{"path": str(path.relative_to(BUILD)), "bytes": path.stat().st_size,
                    "sha256": sha(path)} for path in bit_paths]
        timing = [{"path": str(path.relative_to(BUILD)), "sha256": sha(path),
                   "all_constraints_met": "All Constraints Met" in path.read_text(errors="replace")}
                  for path in timing_paths]
        unchanged = inputs == {name: sha(BUILD / name) for name in inputs}
        passed = code == 0 and "ADV3_PHASE=BITSTREAM_DONE" in body and unchanged
        passed &= bool(outputs) and all(item["bytes"] > 0 for item in outputs)
        passed &= bool(timing) and all(item["all_constraints_met"] for item in timing)
        if receipt["state"] != "TIMEOUT":
            receipt["state"] = "PASS" if passed else "FAIL"
        receipt.update(exit_code=code, elapsed_seconds=round(time.monotonic() - tick, 1),
                       console_sha256=sha(EVIDENCE / "console.log"), inputs_unchanged=unchanged,
                       bitstreams=outputs, timing=timing)
        save(receipt)
        print(json.dumps({key: receipt[key] for key in
                          ("state", "exit_code", "elapsed_seconds", "bitstreams", "timing")}), flush=True)
        print(body[-1000:], flush=True)
        if receipt["state"] != "PASS":
            raise RuntimeError("Isolated seed-2 bitstream build failed validation")
    finally:
        subprocess.run(["subst", drive, "/D"], check=True)


if __name__ == "__main__":
    main()
