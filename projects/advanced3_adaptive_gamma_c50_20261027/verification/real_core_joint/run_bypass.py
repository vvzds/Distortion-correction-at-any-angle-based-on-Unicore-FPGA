"""Exercise the identical joint binary with Gamma disabled and identity mapping."""

import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APP = Path(os.environ.get("IVERILOG_APP", r"C:\Users\lenovo\Documents\Codex\2026-10-11\w-m\work\simulator\iverilog\app"))
OUT = HERE / "bypass_identity"
OUT.mkdir(exist_ok=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(data):
    (OUT / "receipt.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parent = json.loads((HERE / "receipt.json").read_text(encoding="utf-8"))
    assert parent["state"] == "PASS"
    assert all(sha(ROOT / path) == digest for path, digest in parent["inputs"].items())
    image = HERE / "sim.vvp"
    receipt = {"state": "STARTING", "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "parent_receipt_sha256": sha(HERE / "receipt.json"), "sim_sha256": sha(image)}
    save(receipt)
    free = [letter + ":" for letter in "YXWVUTSRQ" if not Path(letter + ":/").exists()]
    project_drive, tool_drive = free[:2]
    subprocess.run(["subst", project_drive, str(ROOT)], check=True)
    subprocess.run(["subst", tool_drive, str(APP)], check=True)
    try:
        args = ["+TEST=0", "+PATTERN=1", "+DDR_WAIT=64", "+GRANT_WAIT=16",
                "+DDR_GAP=3", "+STRIDE=64", "+GAMMA_ENABLE=0", "+GAMMA_SEED=1",
                "+RESULT=result.txt"]
        command = [str(Path(tool_drive + "/bin/vvp.exe")),
                   str(Path(project_drive + "/verification/real_core_joint/sim.vvp"))] + args
        receipt.update(state="RUNNING", command=command)
        save(receipt)
        start = time.monotonic()
        with (OUT / "simulation.log").open("wb") as stream:
            try:
                rc = subprocess.run(command, cwd=OUT, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=5400, creationflags=subprocess.CREATE_NO_WINDOW).returncode
            except subprocess.TimeoutExpired:
                rc = 124
        result = (OUT / "result.txt").read_text(errors="replace") if (OUT / "result.txt").exists() else ""
        receipt.update(state="PASS" if rc == 0 and "=== ALL TESTS PASSED (err=0) ===" in result
                       and "GAMMA enable=0 seed=1 checked=2073600 changed=0" in result else "FAIL",
                       rc=rc, wall_s=round(time.monotonic() - start, 2),
                       simulation_sha256=sha(OUT / "simulation.log"),
                       result_sha256=sha(OUT / "result.txt") if (OUT / "result.txt").exists() else None,
                       inputs_unchanged=all(sha(ROOT / path) == digest for path, digest in parent["inputs"].items()))
        if not receipt["inputs_unchanged"]:
            receipt["state"] = "FAIL"
        save(receipt)
        print(json.dumps({key: receipt[key] for key in ("state", "rc", "wall_s", "inputs_unchanged")}))
        print(result[-1400:])
        if receipt["state"] != "PASS":
            raise RuntimeError("bypass joint regression failed")
    finally:
        subprocess.run(["subst", tool_drive, "/D"], check=True)
        subprocess.run(["subst", project_drive, "/D"], check=True)


if __name__ == "__main__":
    main()
