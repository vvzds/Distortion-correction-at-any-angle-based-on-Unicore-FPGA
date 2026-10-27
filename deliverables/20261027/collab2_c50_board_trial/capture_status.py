"""Record C50 board publication status without modifying FPGA parameters."""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
BITSTREAM = Path(r"D:\FPGA PDS\yx\C23_core30_20261026\host_c50\generate_bitstream\hdmi_ddr_ov5640_top.sbit")
UART_TOOL = Path(r"D:\FPGA PDS\yx\DCSjingtaijiaozheng\04_uart_tool\uart_tool.py")

spec = importlib.util.spec_from_file_location("uart_tool", UART_TOOL)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

samples = []
connection = tool.open_serial("COM11")
try:
    for _ in range(12):
        connection.write(tool.frame(5))
        connection.flush()
        before = time.monotonic()
        status = tool.read_status_frame(connection)
        after = time.monotonic()
        samples.append({
            "monotonic_s": (before + after) / 2,
            "status_hex": f"{status:08X}",
            "pub_count": status >> 16,
            "params_valid": bool(status & 0x100),
            "frame_busy": bool(status & 0x200),
        })
        time.sleep(1)
finally:
    connection.close()

count = (samples[-1]["pub_count"] - samples[0]["pub_count"]) & 0xFFFF
duration = samples[-1]["monotonic_s"] - samples[0]["monotonic_s"]
record = {
    "timestamp": datetime.datetime.now().astimezone().isoformat(),
    "bitstream": str(BITSTREAM),
    "bitstream_sha256": hashlib.sha256(BITSTREAM.read_bytes()).hexdigest(),
    "uart_port": "COM11",
    "samples": samples,
    "publication_delta": count,
    "duration_s": duration,
    "publication_per_s": count / duration,
    "meaning": "Count increments after a complete corrected-frame write; it is not HDMI refresh or distinct camera frame rate.",
}
(ROOT / "board_status.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Complete-frame publications: {count / duration:.3f}/s over {duration:.3f}s")
