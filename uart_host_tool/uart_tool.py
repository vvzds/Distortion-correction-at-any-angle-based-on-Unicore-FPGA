#!/usr/bin/env python3
"""FPGA param_mgr V1.2 的 Python 3.8+ UART 参数工具。"""

import argparse
import csv
import json
import math
import struct
import sys
import time
from pathlib import Path


BAUD_RATE = 115200
READ_TIMEOUT = 1.5
HEADER = b"\xaa\x55"
DISTORTION = ("fx", "fy", "cx", "cy", "k1", "k2", "p1", "p2")
AFFINE = ("a11", "a12", "a21", "a22", "tx", "ty")
CSV_HEADER = DISTORTION + AFFINE + ("aff_en", "gamma_en")
LIMITS = {
    "fx": (128.0, 32767.99), "fy": (128.0, 32767.99),
    "cx": (0.0, 1919.0), "cy": (0.0, 1079.0),
    "k1": (-0.5, 0.5), "k2": (-0.5, 0.5),
    "p1": (-0.01, 0.01), "p2": (-0.01, 0.01),
    "a11": (-2.0, 2.0), "a12": (-2.0, 2.0),
    "a21": (-2.0, 2.0), "a22": (-2.0, 2.0),
    "tx": (-4096.0, 4096.0), "ty": (-4096.0, 4096.0),
}
PAYLOAD_LENGTHS = {0x01: 32, 0x02: 25, 0x03: 256, 0x04: 4, 0x05: 0}


class ToolError(Exception):
    """向用户显示的协议、参数或串口错误。"""


def encode_q16(value):
    """统一的 Q16.16 有符号编码入口。"""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ToolError("参数不是有效数字: {!r}".format(value)) from exc
    if not math.isfinite(number):
        raise ToolError("参数必须是有限数字: {!r}".format(value))
    # 极大但有限的浮点数相乘可能变成 inf，统一转为用户可读错误。
    scaled = number * 65536
    if not math.isfinite(scaled):
        raise ToolError("参数超出 Q16.16 有符号 32 位可表示范围: {}".format(number))
    raw = int(round(scaled))
    if not -(1 << 31) <= raw <= (1 << 31) - 1:
        raise ToolError("参数超出 Q16.16 有符号 32 位可表示范围: {}".format(number))
    return struct.pack("<i", raw)


def decode_q16(data):
    if len(data) != 4:
        raise ToolError("Q16.16 解码需要恰好 4 字节")
    return struct.unpack("<i", data)[0] / 65536.0


def validate_parameters(values, force=False):
    for name, value in values.items():
        if name not in LIMITS:
            raise ToolError("未知参数: {}".format(name))
        try:
            encode_q16(value)
            number = float(value)
        except ToolError as exc:
            raise ToolError("参数 {}: {}".format(name, exc)) from exc
        low, high = LIMITS[name]
        if not force and not low <= number <= high:
            raise ToolError("参数 {}={} 越界；允许范围 [{}, {}]；可用 --force 强制发送".format(
                name, number, low, high))


def warn_reference_limits(values, output=print):
    # 协议允许 ±4096，任务包内 param_mgr.v 当前 T_LIM 却是 0x01000000 (±256)。
    for name in ("tx", "ty"):
        if name in values and abs(float(values[name])) > 256.0:
            output("警告: {}={} 符合协议范围，但附件 param_mgr.v 当前只接受 ±256；"
                   "该 FPGA 版本可能拒绝整组参数".format(name, values[name]))


def frame(cmd, payload=b"", channel=None):
    if cmd not in PAYLOAD_LENGTHS:
        raise ToolError("未知命令: 0x{:02X}".format(cmd))
    if not isinstance(payload, bytes) or len(payload) != PAYLOAD_LENGTHS[cmd]:
        raise ToolError("0x{:02X} 的负载必须恰好 {} 字节".format(
            cmd, PAYLOAD_LENGTHS[cmd]))
    if cmd == 0x03:
        if channel not in (0, 1, 2):
            raise ToolError("Gamma 通道必须是 0、1 或 2")
        length_field = channel
    else:
        if channel is not None:
            raise ToolError("只有 0x03 可以指定通道")
        length_field = len(payload)
    return HEADER + bytes((cmd, length_field)) + payload + bytes((sum(payload) & 0xFF,))


def parse_frame(data, status_reply=False):
    if len(data) < 5 or data[:2] != HEADER:
        raise ToolError("UART 帧头错误或帧不完整")
    cmd, length_field = data[2], data[3]
    if cmd not in PAYLOAD_LENGTHS:
        raise ToolError("未知 UART 命令: 0x{:02X}".format(cmd))
    expected = 4 if status_reply and cmd == 0x05 else PAYLOAD_LENGTHS[cmd]
    if cmd == 0x03:
        if length_field not in (0, 1, 2):
            raise ToolError("Gamma 通道号无效: {}".format(length_field))
    elif length_field != expected:
        raise ToolError("0x{:02X} 长度字段错误: {}，应为 {}".format(
            cmd, length_field, expected))
    if len(data) != 5 + expected:
        raise ToolError("0x{:02X} 帧长度错误: {}，应为 {}".format(
            cmd, len(data), 5 + expected))
    payload = data[4:-1]
    if data[-1] != sum(payload) & 0xFF:
        raise ToolError("0x{:02X} 校验和错误: 收到 {:02X}，应为 {:02X}".format(
            cmd, data[-1], sum(payload) & 0xFF))
    return cmd, length_field, payload


def build_distortion(values, force=False):
    if set(values) != set(DISTORTION):
        raise ToolError("0x01 需要 fx,fy,cx,cy,k1,k2,p1,p2")
    validate_parameters(values, force)
    return frame(0x01, b"".join(encode_q16(values[name]) for name in DISTORTION))


def build_affine(values, enable=0, force=False):
    if set(values) != set(AFFINE):
        raise ToolError("0x02 需要 a11,a12,a21,a22,tx,ty")
    if enable not in (0, 1):
        raise ToolError("aff_en 必须为 0 或 1")
    validate_parameters(values, force)
    payload = b"".join(encode_q16(values[name]) for name in AFFINE) + bytes((enable,))
    return frame(0x02, payload)


def build_gamma(channel, lookup):
    if len(lookup) != 256 or any(not isinstance(v, int) or not 0 <= v <= 255 for v in lookup):
        raise ToolError("Gamma LUT 必须恰好有 256 个 0–255 的整数")
    return frame(0x03, bytes(lookup), channel)


def build_mode(gamma_enable):
    if gamma_enable not in (0, 1):
        raise ToolError("gamma_en 必须为 0 或 1")
    return frame(0x04, struct.pack("<I", gamma_enable))


def identity_lut():
    return list(range(256))


def gamma22_lut():
    return [round(255 * (index / 255) ** 2.2) for index in range(256)]


def load_lut(path, file_format="auto"):
    source = Path(path)
    if file_format not in ("auto", "text", "binary"):
        raise ToolError("LUT 文件格式必须是 auto、text 或 binary")
    if file_format == "auto":
        file_format = "binary" if source.suffix.lower() == ".bin" else "text"
    if file_format == "binary":
        data = source.read_bytes()
        if len(data) != 256:
            raise ToolError("二进制 LUT 必须恰好 256 字节，实际 {} 字节".format(len(data)))
        return list(data)
    values = []
    with source.open("r", encoding="utf-8-sig") as input_file:
        for line_number, line in enumerate(input_file, 1):
            value = line.split("#", 1)[0].strip()
            if not value:
                continue
            if not value.isascii() or not value.isdecimal():
                raise ToolError("LUT 第 {} 行需要 0–255 十进制整数".format(line_number))
            number = int(value, 10)
            if not 0 <= number <= 255:
                raise ToolError("LUT 第 {} 行超出 0–255".format(line_number))
            values.append(number)
    if len(values) != 256:
        raise ToolError("文本 LUT 需要恰好 256 个数据行，实际 {} 行".format(len(values)))
    return values


def parse_assignments(text, names, required=()):
    values = dict.fromkeys(names, 0.0)
    seen = set()
    for item in text.split(","):
        if "=" not in item:
            raise ToolError("参数格式应为 name=value，多个参数用逗号分隔")
        name, raw = (part.strip() for part in item.split("=", 1))
        if name not in values:
            raise ToolError("未知参数: {}".format(name))
        if name in seen:
            raise ToolError("参数重复: {}".format(name))
        seen.add(name)
        try:
            values[name] = float(raw)
        except ValueError as exc:
            raise ToolError("参数 {} 不是数字: {}".format(name, raw)) from exc
    missing = set(required) - seen
    if missing:
        raise ToolError("缺少必需参数: {}".format(",".join(sorted(missing))))
    return values


def load_csv(path, force=False):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as input_file:
        reader = csv.reader(line for line in input_file if line.strip() and
                            not line.lstrip().startswith("#"))
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ToolError("CSV 文件没有表头") from exc
        if tuple(header) != CSV_HEADER:
            raise ToolError("CSV 表头或顺序错误；应为: {}".format(",".join(CSV_HEADER)))
        rows = []
        for row_number, row in enumerate(reader, 1):
            if len(row) != len(CSV_HEADER):
                raise ToolError("CSV 数据行 {} 应有 {} 列，实际 {} 列".format(
                    row_number, len(CSV_HEADER), len(row)))
            values = {}
            for name, raw in zip(CSV_HEADER[:14], row[:14]):
                try:
                    values[name] = float(raw)
                except ValueError as exc:
                    raise ToolError("CSV 数据行 {} 的 {} 不是数字".format(row_number, name)) from exc
            for name, raw in zip(CSV_HEADER[14:], row[14:]):
                if raw.strip() not in ("0", "1"):
                    raise ToolError("CSV 数据行 {} 的 {} 必须为 0 或 1".format(row_number, name))
                values[name] = int(raw.strip())
            validate_parameters({name: values[name] for name in DISTORTION + AFFINE}, force)
            rows.append(values)
    if not rows:
        raise ToolError("CSV 文件没有参数数据行")
    return rows


def build_csv_sequence(rows, force=False):
    result = []
    for row_number, row in enumerate(rows, 1):
        result.append(("参数集 {} / 0x01".format(row_number),
                       build_distortion({name: row[name] for name in DISTORTION}, force)))
        result.append(("参数集 {} / 0x02".format(row_number),
                       build_affine({name: row[name] for name in AFFINE}, row["aff_en"], force)))
        result.append(("参数集 {} / 0x04".format(row_number), build_mode(row["gamma_en"])))
    return result


def hex_dump(data):
    return " ".join("{:02X}".format(byte) for byte in data)


def open_serial(port):
    try:
        import serial
    except ImportError as exc:
        raise ToolError("缺少 pyserial；请先运行 pip install pyserial") from exc
    try:
        return serial.Serial(port=port, baudrate=BAUD_RATE, bytesize=serial.EIGHTBITS,
                             parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                             timeout=READ_TIMEOUT, write_timeout=READ_TIMEOUT,
                             xonxoff=False, rtscts=False, dsrdtr=False)
    except (serial.SerialException, ValueError) as exc:
        raise ToolError("串口 {} 打开失败: {}".format(port, exc)) from exc


def send_sequence(port, sequence, force=False, opener=open_serial, output=print):
    # 下行命令没有 ACK；这里只能确认帧本身合法、完整写入驱动并 flush。
    with opener(port) as connection:
        for label, data in sequence:
            parse_frame(data)
            output("{}发送 [{}]: {}".format("FORCED/OVERRIDE " if force else "", label,
                                         hex_dump(data)))
            try:
                sent = connection.write(data)
                connection.flush()
            except Exception as exc:
                raise ToolError("串口发送失败 [{}]: {}".format(label, exc)) from exc
            if sent != len(data):
                raise ToolError("串口短写 [{}]: {} / {} 字节".format(label, sent, len(data)))


def _read_exact(connection, count, deadline, clock):
    result = bytearray()
    while len(result) < count:
        if clock() >= deadline:
            raise ToolError("状态回读超时：尚缺 {} 字节".format(count - len(result)))
        try:
            part = connection.read(count - len(result))
        except Exception as exc:
            raise ToolError("串口接收失败: {}".format(exc)) from exc
        if part:
            result.extend(part)
    return bytes(result)


def read_status_frame(connection, timeout=READ_TIMEOUT, clock=time.monotonic):
    if timeout < 1.0:
        raise ToolError("状态接收超时必须至少 1 秒")
    deadline = clock() + timeout
    saw_aa = False
    while True:
        value = _read_exact(connection, 1, deadline, clock)[0]
        if saw_aa and value == 0x55:
            break
        saw_aa = value == 0xAA
    command_and_length = _read_exact(connection, 2, deadline, clock)
    if command_and_length != b"\x05\x04":
        raise ToolError("状态回读命令或长度错误: {}".format(hex_dump(command_and_length)))
    response = HEADER + command_and_length + _read_exact(connection, 5, deadline, clock)
    _, _, payload = parse_frame(response, status_reply=True)
    return struct.unpack("<I", payload)[0]


def format_status(status, status_map=None):
    lines = ["状态: 0x{:08X} ({})".format(status, status)]
    if status_map is None:
        return "\n".join(lines)
    with Path(status_map).open("r", encoding="utf-8") as input_file:
        mapping = json.load(input_file)
    if not isinstance(mapping, dict) or not isinstance(mapping.get("fields"), dict):
        raise ToolError("状态映射 JSON 需要 fields 对象")
    for name, definition in mapping["fields"].items():
        if not isinstance(definition, dict):
            raise ToolError("状态字段 {} 定义无效".format(name))
        lsb = definition.get("bit", definition.get("lsb"))
        width = definition.get("width", 1)
        if (type(lsb) is not int or type(width) is not int or not 0 <= lsb < 32 or
                not 1 <= width <= 32 - lsb):
            raise ToolError("状态字段 {} 的位范围无效".format(name))
        value = (status >> lsb) & ((1 << width) - 1)
        lines.append("{}: 0x{:X} ({})".format(name, value, value))
    return "\n".join(lines)


def query_status(port, status_map=None, opener=open_serial, output=print,
                 clock=time.monotonic):
    request = frame(0x05)
    with opener(port) as connection:
        output("发送 [状态请求]: {}".format(hex_dump(request)))
        try:
            connection.reset_input_buffer()
            sent = connection.write(request)
            connection.flush()
        except Exception as exc:
            raise ToolError("状态请求发送失败: {}".format(exc)) from exc
        if sent != len(request):
            raise ToolError("状态请求短写: {} / {} 字节".format(sent, len(request)))
        status = read_status_frame(connection, clock=clock)
        output(format_status(status, status_map))
        return status


def list_ports(output=print):
    try:
        from serial.tools import list_ports as serial_list_ports
    except ImportError as exc:
        raise ToolError("缺少 pyserial；请先运行 pip install pyserial") from exc
    found = sorted(serial_list_ports.comports(), key=lambda item: item.device)
    if not found:
        output("未发现可用串口")
    for item in found:
        output("{}  {}".format(item.device, item.description))
    return found


def build_parser():
    parser = argparse.ArgumentParser(description="FPGA 畸变校正参数 UART 工具 (V1.2)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="枚举串口")
    commands.add_parser("selftest", help="无硬件 U0–U5 自测")
    for command in ("send-0x01", "send-0x02", "send-0x03", "send-0x04",
                    "read-0x05", "send-file"):
        sub = commands.add_parser(command)
        sub.add_argument("--port", required=True, help="串口，例如 COM3")
        if command in ("send-0x01", "send-0x02", "send-file"):
            sub.add_argument("--force", action="store_true", help="跳过 G02 范围预检")
        if command == "send-0x01":
            sub.add_argument("--params", required=True, help="fx=...,fy=...,cx=...,cy=...[,k1=...]")
        elif command == "send-0x02":
            sub.add_argument("--affine", default="a11=0,a12=0,a21=0,a22=0,tx=0,ty=0")
            sub.add_argument("--en", type=int, choices=(0, 1), default=0)
        elif command == "send-0x03":
            source = sub.add_mutually_exclusive_group(required=True)
            source.add_argument("--preset", choices=("identity", "gamma2.2"))
            source.add_argument("--file", help="256 行文本 LUT 或 256 字节二进制 LUT")
            sub.add_argument("--format", choices=("auto", "text", "binary"), default="auto")
            sub.add_argument("--channel", choices=("0", "1", "2", "all"), default="all")
        elif command == "send-0x04":
            sub.add_argument("--gamma-en", type=int, choices=(0, 1), required=True)
        elif command == "read-0x05":
            sub.add_argument("--status-map", help="可选状态位域 JSON 文件")
        elif command == "send-file":
            sub.add_argument("--csv", required=True, help="冻结表头的 UTF-8 参数 CSV")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.command == "selftest":
            from tests.selftest import run_selftest
            return run_selftest()
        if args.command == "list":
            list_ports()
            return 0
        if args.command == "send-0x01":
            values = parse_assignments(args.params, DISTORTION, DISTORTION[:4])
            sequence = [("0x01 畸变参数", build_distortion(values, args.force))]
        elif args.command == "send-0x02":
            values = parse_assignments(args.affine, AFFINE)
            sequence = [("0x02 仿射参数", build_affine(values, args.en, args.force))]
            warn_reference_limits(values)
        elif args.command == "send-0x03":
            lut = (identity_lut() if args.preset == "identity" else gamma22_lut()) if args.preset else \
                load_lut(args.file, args.format)
            channels = (0, 1, 2) if args.channel == "all" else (int(args.channel),)
            sequence = [("0x03 Gamma 通道 {}".format(channel), build_gamma(channel, lut))
                        for channel in channels]
        elif args.command == "send-0x04":
            sequence = [("0x04 模式", build_mode(args.gamma_en))]
        elif args.command == "send-file":
            rows = load_csv(args.csv, args.force)
            sequence = build_csv_sequence(rows, args.force)
            for index, values in enumerate(rows, 1):
                warn_reference_limits(values, output=lambda message, row=index:
                                      print("参数集 {}: {}".format(row, message)))
        else:
            query_status(args.port, args.status_map)
            return 0
        send_sequence(args.port, sequence, getattr(args, "force", False))
        return 0
    except (ToolError, OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        print("错误: {}".format(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
