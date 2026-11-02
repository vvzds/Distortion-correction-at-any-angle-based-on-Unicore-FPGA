"""BNO085 quaternion/gyro snapshots from the autonomous FPGA SPI bridge.

SH-2 numeric definitions follow CEVA sh2 SDK; no sensor-flash writes. Quaternion
is i,j,k,real (Q14), calibrated gyro rad/s (Q9), GIRV angular velocity Q10.
"""
import struct
import numpy as np

from protocol import Connection, packet

MODES = {'game': 0, 'arvr-game': 1, 'girv': 2}
REPORT_IDS = {0: 0x08, 1: 0x29, 2: 0x2a}


def quaternion_rotation(value):
    q = np.asarray(value, dtype=float)
    if q.shape != (4,) or not np.isfinite(q).all():
        raise ValueError('Invalid BNO quaternion')
    norm = np.linalg.norm(q)
    if not .85 <= norm <= 1.15:
        raise ValueError(f'BNO quaternion norm {norm:.3f} outside envelope')
    x, y, z, w = q/norm
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def parse_snapshot(payload):
    if len(payload) != 48:
        raise ValueError('Wrong BNO snapshot length')
    magic, now, frame_us, frames, gyro_us = struct.unpack_from('<5I', payload)
    if magic != 0x424e4f01:
        raise ValueError('BNO085 SPI firmware required; JY901P image is incompatible')
    pose_us = struct.unpack_from('<I', payload, 28)[0]
    errors, flags = struct.unpack_from('<2I', payload, 40)
    mode = flags >> 29
    seen = (flags >> 24) & 3
    if mode not in REPORT_IDS:
        raise ValueError('Unknown BNO report mode')
    gyro = np.array(struct.unpack_from('<3h', payload, 20), dtype=float)/(1024 if mode == 2 else 512)
    q = np.array(struct.unpack_from('<4h', payload, 32), dtype=float)/16384
    r = quaternion_rotation(q) if seen & 2 else np.eye(3)
    # Euler is diagnostic text only; rotation control uses r directly.
    euler = np.rad2deg([np.arctan2(r[2,1], r[2,2]),
                       np.arcsin(np.clip(-r[2,0], -1, 1)), np.arctan2(r[1,0], r[0,0])])
    return dict(now=now, frame_us=frame_us, frames=frames, gyro_us=gyro_us,
                gyro=np.rad2deg(gyro), angle_us=pose_us, euler=euler,
                quaternion=q, rotation=r, errors=errors, packets=flags & 0xffffff,
                seen=seen, mode=mode, generation=struct.unpack_from('<H', payload, 26)[0])


def parse_diagnostics(payload):
    if len(payload) != 48:
        raise ValueError('Wrong BNO diagnostic length')
    v = struct.unpack('<12I', payload)
    if v[0] != 0x424e4401:
        raise ValueError('BNO085 diagnostics required')
    return dict(now=v[1], requested_us=v[2], report_id=v[3]&255, status=(v[3]>>8)&255,
                version_major=v[3]>>24, version_minor=(v[3]>>16)&255,
                resets=v[4], sequence_gaps=v[5], oversize=v[6], transactions=v[7],
                pose_interval_us=v[8], gyro_interval_us=v[9], part=v[10], build=v[11])


class BnoConnection(Connection):
    def imu_state(self):
        seq = self.next_sequence()
        self.serial.write(packet(0x22, seq))
        return parse_snapshot(self._receive(0xa2, seq, timeout=.3))

    def diagnostics(self):
        seq = self.next_sequence()
        self.serial.write(packet(0x25, seq))
        return parse_diagnostics(self._receive(0xa5, seq, timeout=.3))

    def set_mode(self, name):
        mode = MODES[name]
        self.serial.write(packet(0x23, self.next_sequence(), bytes([mode])))
        state = self.imu_state()
        if state['mode'] != mode:
            raise RuntimeError('BNO report mode readback mismatch')
        return state

    def restart(self):
        """Explicit volatile sensor reset/reconfiguration; no persistent writes."""
        self.serial.write(packet(0x24, self.next_sequence()))


class ShtpDecoder:
    """Offline reference decoder for full SPI transfers (zero padded allowed).

    Complete cargos only; reject continuation/truncation rather than guessing.
    Timestamp is FPGA host-interrupt time; SH2 delay units are 100us. This is
    the golden model for RTL, not a second serial transport used at runtime.
    """
    LENGTHS = {0xfb:5, 0xfa:5, 0x02:10, 0x08:12, 0x29:12, 0x05:14,
               0x09:14, 0x28:14, 0xf8:16, 0xfc:17, 0xf1:16, 0xef:2}
    def __init__(self):
        self.sequences = {}
        self.gaps = 0

    def decode(self, data, interrupt_us, mode='game'):
        if len(data) < 4:
            raise ValueError('Short SHTP header')
        length, channel, sequence = struct.unpack_from('<HBB', data)
        if length == 0:
            return []
        if length & 0x8000 or not 4 <= length <= 516 or length > len(data) or channel > 5:
            raise ValueError('SHTP unsupported continuation, oversize or truncated cargo')
        if channel in self.sequences and sequence != self.sequences[channel]:
            self.gaps += 1
        self.sequences[channel] = (sequence+1)&255
        payload = data[4:length]
        if channel == 0:
            return []
        if channel == 1:
            return [dict(reset=True)] if payload[:1] == b'\x01' else []
        cursor, delta, result = 0, 0, []
        while cursor < len(payload):
            if channel == 5:
                if mode != 'girv' or len(payload)-cursor < 14:
                    raise ValueError('GIRV length/mode mismatch')
                v = struct.unpack_from('<7h', payload, cursor)
                result.append(dict(quaternion=np.array(v[:4])/16384,
                                   gyro_rad_s=np.array(v[4:])/1024, stamp=interrupt_us))
                cursor += 14
                continue
            report = payload[cursor]
            size = self.LENGTHS.get(report)
            if size is None or cursor+size > len(payload):
                raise ValueError('Unknown or truncated SH2 report')
            data = payload[cursor:cursor+size]
            if channel in (3,4):
                if report == 0xfb:
                    delta = -struct.unpack_from('<i', data, 1)[0]
                elif report == 0xfa:
                    delta += struct.unpack_from('<i', data, 1)[0]
                else:
                    delay = ((data[2]&0xfc)<<6)+data[3]
                    stamp = (interrupt_us+(delta+delay)*100)&0xffffffff
                    if report in (8,0x29):
                        q = np.array(struct.unpack_from('<4h', data, 4))/16384
                        quaternion_rotation(q)
                        result.append(dict(quaternion=q, stamp=stamp, report_id=report))
                    elif report == 2:
                        result.append(dict(gyro_rad_s=np.array(struct.unpack_from('<3h', data, 4))/512,
                                           stamp=stamp, report_id=report))
            elif channel == 2:
                result.append(dict(control_report=report, data=data.hex()))
            cursor += size
        return result
