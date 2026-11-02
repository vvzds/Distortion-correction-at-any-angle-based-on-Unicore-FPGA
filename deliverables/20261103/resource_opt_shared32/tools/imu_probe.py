"""Bridge diagnostics (opens only explicitly selected board UART).

No matrices, capture card or JTAG. BNO mode has autonomous FPGA initialization;
explicit --bno-report/--restart-bno requests can reconfigure/reset the sensor.
JY receiver baud selection changes only FPGA RX, never the sensor setting.
"""
import argparse
import json
from pathlib import Path
import sys
import time
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'host'))
from imu import BAUD_CODES, ImuConnection, PoseHistory, signed_us
from bno085 import BnoConnection, MODES


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', required=True)
    p.add_argument('--seconds', type=float, default=5)
    p.add_argument('--imu-baud', type=int, choices=BAUD_CODES)
    p.add_argument('--sensor', choices=['jy901p','bno085'], default='jy901p')
    p.add_argument('--bno-report', choices=MODES, help='Explicitly select/reset BNO feature mode (volatile)')
    p.add_argument('--restart-bno', action='store_true', help='Explicit hardware reset, not an automatic probe action')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if not 1 <= a.seconds <= 60:
        p.error('Duration must be 1..60 seconds')
    if a.output.exists():
        p.error('Use a new output file')
    history, records = PoseHistory(), []
    if a.sensor == 'bno085' and a.imu_baud is not None:
        p.error('BNO085 SPI has no IMU UART baud setting')
    link = (BnoConnection if a.sensor == 'bno085' else ImuConnection)(a.port)
    try:
        if a.imu_baud is not None:
            link.receiver_baud(a.imu_baud)
        if a.sensor == 'bno085' and a.bno_report:
            link.set_mode(a.bno_report)
        if a.sensor == 'bno085' and a.restart_bno:
            link.restart()
        start = time.monotonic()
        while time.monotonic()-start < a.seconds:
            state = link.imu_state()
            if (records and a.sensor=='bno085' and state['generation']!=records[-1]['generation']):
                history=PoseHistory()
            history.append(state)
            records.append(dict(host=time.monotonic(), **state))
            time.sleep(.002)
        health = link.status()
        diagnostics = link.diagnostics() if a.sensor=='bno085' else None
        last = records[-1]
        result = dict(sensor=a.sensor, probe_sends_sensor_commands=bool(a.bno_report or a.restart_bno),
                      fpga_autonomous_sensor_config=(a.sensor=='bno085'),
                      matrix_writes=0, capture_opened=False, diagnostics=diagnostics,
                      elapsed=time.monotonic()-start, rate=history.rate(),
                      gyro_age_ms=1000*signed_us(last['now'], last['gyro_us']),
                      angle_age_ms=1000*signed_us(last['now'], last['angle_us']),
                      last=last, health=health, records=records)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(result, indent=2, default=lambda v:v.tolist()), encoding='utf-8')
        result.pop('records')
        print(json.dumps(result, indent=2, default=lambda v:v.tolist()))
    finally:
        link.close()


if __name__ == '__main__':
    main()
