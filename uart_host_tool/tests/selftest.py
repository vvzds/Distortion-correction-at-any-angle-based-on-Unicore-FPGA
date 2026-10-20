"""不依赖 pyserial 或 FPGA 的 U0–U5 自测。"""

import json
import random
import re
import struct
import sys
import tempfile
import types
from pathlib import Path

import uart_tool as tool


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DISTORTION = {
    "fx": 1000.0, "fy": 1000.0, "cx": 960.0, "cy": 540.0,
    "k1": 0.0, "k2": 0.0, "p1": 0.0, "p2": 0.0,
}
SAMPLE_AFFINE = {
    "a11": 1.0, "a12": 0.0, "a21": 0.0,
    "a22": 1.0, "tx": 0.0, "ty": 0.0,
}

# V2 原文在 0x20 长度字段后实际有 34 个负载字节，且校验写 B8。
# 下方是遵照协议规格 §2 (32B) 和 §1 (负载字节和) 的逐字节预期。
V2_PROTOCOL = bytes.fromhex(
    "AA 55 01 20 00 00 E8 03 00 00 E8 03 00 00 C0 03 00 00 1C 02 "
    + "00 00 00 00 " * 4 + "B7"
)
V2_DOCUMENTED = bytes.fromhex(
    "AA 55 01 20 00 00 E8 03 00 00 E8 03 00 00 C0 03 00 00 1C 02 "
    + "00 00 00 00 " * 4 + "00 00 B8"
)


def raises(error_type, action, contains=None):
    try:
        action()
    except error_type as exc:
        if contains is not None:
            assert contains in str(exc), "错误定位不清: {}".format(exc)
        return exc
    raise AssertionError("预期出现 {}，实际没有".format(error_type.__name__))


class MockSerial:
    def __init__(self, reply=None, echo=False, short_write=False, read_chunk=None):
        self.writes = []
        self.buffer = bytearray(reply or b"")
        self.echo = echo
        self.short_write = short_write
        self.read_chunk = read_chunk
        self.flush_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def write(self, data):
        self.writes.append(bytes(data))
        if self.echo:
            self.buffer.extend(data)
        return len(data) - (1 if self.short_write else 0)

    def flush(self):
        self.flush_count += 1

    def reset_input_buffer(self):
        # 回读测试在发送后注入预设应答；不丢弃测试夹具中的预设内容。
        pass

    def read(self, count):
        if self.read_chunk is not None:
            count = min(count, self.read_chunk)
        data = bytes(self.buffer[:count])
        del self.buffer[:count]
        return data


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        self.value += 0.1
        return self.value


def u0_frozen_vectors():
    task_text = (ROOT / "reference_original" /
                 "00_TASK_BRIEF_uart_host_tool_v1.0.md").read_text(encoding="utf-8")
    documented = {}
    for label in ("V1", "V2", "V3", "V5"):
        line = next(line for line in task_text.splitlines() if line.startswith("| {} |".format(label)))
        documented[label] = bytes.fromhex(re.search(r"`([^`]+)`", line).group(1))
    assert tool.frame(0x05) == documented["V1"]
    assert documented["V2"] == V2_DOCUMENTED
    assert len(V2_DOCUMENTED) == 39
    raises(tool.ToolError, lambda: tool.parse_frame(V2_DOCUMENTED), "帧长度")
    assert len(V2_PROTOCOL) == 37
    assert V2_PROTOCOL[-1] == 0xB7
    assert tool.build_distortion(SAMPLE_DISTORTION) == V2_PROTOCOL
    assert tool.build_affine(SAMPLE_AFFINE, 1) == documented["V3"] == bytes.fromhex(
        "AA 55 02 19 00 00 01 00 00 00 00 00 00 00 00 00 "
        "00 00 01 00 00 00 00 00 00 00 00 00 01 03")
    assert tool.build_gamma(0, tool.identity_lut()) == (
        bytes.fromhex("AA 55 03 00") + bytes(range(256)) + bytes.fromhex("80"))
    assert tool.build_mode(1) == documented["V5"] == bytes.fromhex("AA 55 04 04 01 00 00 00 01")
    print("U0 V2 已确认勘误: 原文 39B/B8；有效帧 37B/B7")


def u1_q16_roundtrip():
    exact = {
        128.0: 0x00800000, 0.0: 0x00000000,
        0.5: 0x00008000, -0.5: 0xFFFF8000,
        0.01: 0x0000028F, -0.01: 0xFFFFFD71,
        2.0: 0x00020000, -2.0: 0xFFFE0000,
        4096.0: 0x10000000, -4096.0: 0xF0000000,
    }
    for value, expected in exact.items():
        assert struct.unpack("<I", tool.encode_q16(value))[0] == expected
    assert struct.unpack("<I", tool.encode_q16(32767.99))[0] <= 0x7FFFFFFF
    assert struct.unpack("<I", tool.encode_q16(32767.99))[0] == 0x7FFFFD71
    rng = random.Random(20261015)
    for _ in range(1200):
        name = rng.choice(tuple(tool.LIMITS))
        low, high = tool.LIMITS[name]
        value = rng.uniform(low, high)
        assert abs(tool.decode_q16(tool.encode_q16(value)) - value) < 1 / 65536
    raises(tool.ToolError, lambda: tool.encode_q16(float("nan")), "有限")
    raises(tool.ToolError, lambda: tool.encode_q16(32768), "可表示范围")
    for value in (1e308, -1e308):
        raises(tool.ToolError, lambda value=value: tool.encode_q16(value), "可表示范围")
    raises(tool.ToolError, lambda: tool.validate_parameters({"fx": 1e308}), "fx")


def u2_g02_boundaries():
    step = 1 / 65536
    for name, (low, high) in tool.LIMITS.items():
        tool.validate_parameters({name: low})
        tool.validate_parameters({name: high})
        raises(tool.ToolError, lambda name=name, value=low-step:
               tool.validate_parameters({name: value}), name)
        raises(tool.ToolError, lambda name=name, value=high+step:
               tool.validate_parameters({name: value}), name)
        tool.validate_parameters({name: low-step}, force=True)
        tool.validate_parameters({name: high+step}, force=True)
    bad = dict(SAMPLE_DISTORTION, fx=127.0)
    raises(tool.ToolError, lambda: tool.build_distortion(bad), "fx")
    forced = tool.build_distortion(bad, force=True)
    assert tool.parse_frame(forced)[0] == 0x01
    lines = []
    tool.send_sequence("MOCK", [("forced", forced)], force=True,
                       opener=lambda _port: MockSerial(), output=lines.append)
    assert "FORCED/OVERRIDE" in lines[0]
    warnings = []
    tool.validate_parameters({"tx": 257.0})
    tool.warn_reference_limits({"tx": 257.0}, output=warnings.append)
    assert len(warnings) == 1 and "±256" in warnings[0]


def u3_send_loopback():
    lut = tool.gamma22_lut()
    assert len(lut) == 256 and lut[0] == 0 and lut[-1] == 255
    sequence = [
        ("distortion", tool.build_distortion(SAMPLE_DISTORTION)),
        ("affine", tool.build_affine(SAMPLE_AFFINE, 1)),
    ]
    sequence += [("gamma {}".format(ch), tool.build_gamma(ch, lut)) for ch in range(3)]
    sequence += [("mode", tool.build_mode(1)), ("status request", tool.frame(0x05))]
    mock = MockSerial(echo=True)
    output = []
    tool.send_sequence("MOCK", sequence, opener=lambda _port: mock, output=output.append)
    assert mock.writes == [data for _, data in sequence]
    assert mock.flush_count == 7 and len(output) == 7
    assert b"".join(mock.writes) == bytes(mock.buffer)
    for (_, expected), actual in zip(sequence, mock.writes):
        cmd, channel, payload = tool.parse_frame(actual)
        assert cmd == expected[2] and actual == expected
        if cmd == 0x03:
            assert channel in (0, 1, 2) and len(payload) == 256
    for invalid in (bytes.fromhex("AA 55 02 18") + bytes(24) + b"\x00",
                    bytes.fromhex("AA 55 03 03") + bytes(256) + b"\x00"):
        raises(tool.ToolError, lambda data=invalid: tool.parse_frame(data))
    short = MockSerial(short_write=True)
    raises(tool.ToolError, lambda: tool.send_sequence(
        "MOCK", sequence[:1], opener=lambda _port: short, output=lambda _line: None), "短写")

    # 用注入模块核对真实串口入口的物理层配置，无需安装 pyserial。
    saved = {name: sys.modules.get(name) for name in
             ("serial", "serial.tools", "serial.tools.list_ports")}
    options = {}
    serial_module = types.ModuleType("serial")
    serial_module.__path__ = []
    serial_module.EIGHTBITS = 8
    serial_module.PARITY_NONE = "N"
    serial_module.STOPBITS_ONE = 1
    serial_module.SerialException = OSError

    def fake_open(**kwargs):
        options.update(kwargs)
        return MockSerial()

    serial_module.Serial = fake_open
    tools_module = types.ModuleType("serial.tools")
    tools_module.__path__ = []
    list_module = types.ModuleType("serial.tools.list_ports")
    list_module.comports = lambda: [types.SimpleNamespace(device="COM7", description="mock")]
    try:
        sys.modules["serial"] = serial_module
        sys.modules["serial.tools"] = tools_module
        sys.modules["serial.tools.list_ports"] = list_module
        tool.open_serial("COM7")
        assert options == {
            "port": "COM7", "baudrate": 115200, "bytesize": 8, "parity": "N",
            "stopbits": 1, "timeout": 1.5, "write_timeout": 1.5,
            "xonxoff": False, "rtscts": False, "dsrdtr": False,
        }
        listed = []
        assert len(tool.list_ports(output=listed.append)) == 1
        assert "COM7" in listed[0]
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def u4_status_readback():
    expected = 0xA5A51234
    reply = tool.HEADER + bytes.fromhex("05 04") + struct.pack("<I", expected)
    reply += bytes((sum(reply[4:]) & 0xFF,))
    assert tool.parse_frame(reply, status_reply=True)[2] == struct.pack("<I", expected)
    mock = MockSerial(reply=b"\x00\xAA\xAA" + reply, read_chunk=1)
    output = []
    status = tool.query_status("MOCK", opener=lambda _port: mock,
                               output=output.append, clock=FakeClock())
    assert status == expected and "0xA5A51234" in output[1]
    assert str(expected) in output[1]
    with tempfile.TemporaryDirectory() as directory:
        mapping_file = Path(directory) / "status_map.json"
        mapping_file.write_text(json.dumps({"fields": {
            "flag": {"bit": 2}, "byte": {"lsb": 8, "width": 8}}}),
            encoding="utf-8")
        text = tool.format_status(expected, mapping_file)
        assert "flag: 0x1 (1)" in text and "byte: 0x12 (18)" in text
    bad = MockSerial(reply=reply[:-1] + bytes((reply[-1] ^ 1,)))
    raises(tool.ToolError, lambda: tool.read_status_frame(bad, clock=FakeClock()), "校验和")
    raises(tool.ToolError, lambda: tool.read_status_frame(
        MockSerial(), clock=FakeClock()), "超时")
    raises(tool.ToolError, lambda: tool.read_status_frame(
        MockSerial(reply=reply[:6]), clock=FakeClock()), "超时")
    malformed = MockSerial(reply=b"\xAA\x55\x05\x05")
    raises(tool.ToolError, lambda: tool.read_status_frame(
        malformed, clock=FakeClock()), "长度")


def u5_csv_and_lut_files():
    rows = tool.load_csv(ROOT / "params_template.csv")
    assert len(rows) == 1 and rows[0]["fx"] == 1000.0
    assert rows[0]["aff_en"] == 1 and rows[0]["gamma_en"] == 1
    sequence = tool.build_csv_sequence(rows)
    mock = MockSerial()
    tool.send_sequence("MOCK", sequence, opener=lambda _port: mock,
                       output=lambda _line: None)
    assert [tool.parse_frame(data)[0] for data in mock.writes] == [1, 2, 4]
    assert tool.decode_q16(mock.writes[0][4:8]) == 1000.0
    assert mock.writes[1][-2] == 1 and mock.writes[2][4] == 1
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        binary = directory / "lut.bin"
        text = directory / "lut.txt"
        binary.write_bytes(bytes(range(256)))
        text.write_text("\n".join("{} # index".format(n) for n in range(256)),
                        encoding="utf-8")
        assert tool.load_lut(binary) == tool.identity_lut()
        assert tool.load_lut(text) == tool.identity_lut()
        binary.write_bytes(bytes(255))
        raises(tool.ToolError, lambda: tool.load_lut(binary), "256")
        text.write_text("256\n", encoding="utf-8")
        raises(tool.ToolError, lambda: tool.load_lut(text), "第 1 行")
        csv_file = directory / "invalid.csv"
        contents = (ROOT / "params_template.csv").read_text(encoding="utf-8")
        csv_file.write_text(contents.replace("1000.0,1000.0", "127.0,1000.0"),
                            encoding="utf-8")
        raises(tool.ToolError, lambda: tool.load_csv(csv_file), "fx")
        forced_rows = tool.load_csv(csv_file, force=True)
        assert len(tool.build_csv_sequence(forced_rows, force=True)) == 3
        data_line = next(line for line in contents.splitlines()
                         if line and not line.startswith("#") and not line.startswith("fx,"))
        csv_file.write_text(contents + data_line + "\n", encoding="utf-8")
        assert [tool.parse_frame(data)[0] for _, data in
                tool.build_csv_sequence(tool.load_csv(csv_file))] == [1, 2, 4, 1, 2, 4]


def run_selftest():
    cases = [
        ("U0", u0_frozen_vectors), ("U1", u1_q16_roundtrip),
        ("U2", u2_g02_boundaries), ("U3", u3_send_loopback),
        ("U4", u4_status_readback), ("U5", u5_csv_and_lut_files),
    ]
    failures = 0
    for name, function in cases:
        try:
            function()
        except Exception as exc:
            failures += 1
            print("[{}] FAIL: {}: {}".format(name, type(exc).__name__, exc))
        else:
            print("[{}] PASS".format(name))
    if failures:
        print("=== TESTS FAILED ({}) ===".format(failures))
        return 1
    print("=== ALL TESTS PASSED ===")
    return 0
