"""Run the C50 core / adaptive Gamma / simulated DDR joint regression."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RTL = ROOT / "engineering_candidate" / "source" / "rtl"
APP = Path(os.environ.get("IVERILOG_APP", r"C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\work\simulator\iverilog\app"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(data):
    (HERE / "receipt.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run(command, cwd, log, timeout):
    with log.open("wb") as stream:
        try:
            return subprocess.run(
                command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW,
            ).returncode
        except subprocess.TimeoutExpired:
            return 124


def main():
    sources = [RTL / "corr_subsys" / name for name in (
        "undistort_core.v", "undistort_map.v", "undistort_cache_ab.v",
        "undistort_bilinear.v", "rect_wr_if.v", "adaptive_gamma.v",
        "adaptive_gamma_curve.v",
    )]
    sources += [RTL / name for name in (
        "corr_write_pack.v", "corr_write_arb.v", "corr_read_bridge.v",
    )]
    sources.append(HERE / "core30_gamma_joint_tb.v")
    inputs = {str(path.relative_to(ROOT)): sha(path) for path in sources}
    receipt = {"state": "STARTING", "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "inputs": inputs, "tool_sha256": sha(APP / "bin" / "iverilog.exe")}
    save(receipt)
    free = [letter + ":" for letter in "YXWVUTSRQ" if not Path(letter + ":/").exists()]
    project_drive, tool_drive = free[:2]
    subprocess.run(["subst", project_drive, str(ROOT)], check=True)
    subprocess.run(["subst", tool_drive, str(APP)], check=True)
    try:
        mapped = [str(Path(project_drive + "/") / path.relative_to(ROOT)) for path in sources]
        image = str(Path(project_drive + "/verification/real_core_joint/sim.vvp"))
        compile_cmd = [str(Path(tool_drive + "/bin/iverilog.exe")), "-B",
                       str(Path(tool_drive + "/lib/ivl")), "-I", str(Path(project_drive + "/engineering_candidate")),
                       "-g2012", "-DAB_CANDIDATE", "-s", "core30_system_tb", "-o", image] + mapped
        receipt["compile_command"] = compile_cmd
        rc = run(compile_cmd, HERE, HERE / "compile.log", 180)
        receipt["compile_rc"] = rc
        receipt["compile_sha256"] = sha(HERE / "compile.log")
        save(receipt)
        if rc:
            receipt.update(state="COMPILE_FAIL", error=(HERE / "compile.log").read_text(errors="replace")[-3000:])
            save(receipt)
            raise RuntimeError("compile failed: " + (HERE / "compile.log").read_text(errors="replace")[-3000:])
        args = ["+TEST=10", "+PATTERN=1", "+DDR_WAIT=64", "+GRANT_WAIT=16",
                "+DDR_GAP=3", "+STRIDE=64", "+GAMMA_ENABLE=1", "+GAMMA_SEED=1",
                "+RESULT=result.txt"]
        command = [str(Path(tool_drive + "/bin/vvp.exe")), image] + args
        receipt.update(state="RUNNING", simulation_command=command)
        save(receipt)
        print("JOINT_SIM_RUNNING", flush=True)
        start = time.monotonic()
        rc = run(command, HERE, HERE / "simulation.log", 5400)
        body = (HERE / "simulation.log").read_text(errors="replace")
        result = (HERE / "result.txt").read_text(errors="replace") if (HERE / "result.txt").exists() else ""
        receipt.update(state="PASS" if rc == 0 and "=== ALL TESTS PASSED (err=0) ===" in result
                       and "GAMMA enable=1 seed=1 checked=2073600" in result else "FAIL",
                       simulation_rc=rc, wall_s=round(time.monotonic() - start, 2),
                       simulation_sha256=sha(HERE / "simulation.log"),
                       result_sha256=sha(HERE / "result.txt") if (HERE / "result.txt").exists() else None,
                       inputs_unchanged=inputs == {str(path.relative_to(ROOT)): sha(path) for path in sources})
        if not receipt["inputs_unchanged"]:
            receipt["state"] = "FAIL"
        save(receipt)
        print(json.dumps({key: receipt[key] for key in ("state", "simulation_rc", "wall_s", "inputs_unchanged")}), flush=True)
        print(body[-1000:], flush=True)
        print(result[-1300:], flush=True)
        if receipt["state"] != "PASS":
            raise RuntimeError("joint regression failed")
    finally:
        subprocess.run(["subst", tool_drive, "/D"], check=True)
        subprocess.run(["subst", project_drive, "/D"], check=True)


if __name__ == "__main__":
    main()
