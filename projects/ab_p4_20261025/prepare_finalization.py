"""Prepare reporting/packaging scripts; does not claim or publish results."""
from pathlib import Path
R=Path(__file__).resolve().parent
B=R.parent/'AB_P3缓存实施_20261024'
oldhash='614797ccd5a2f122caed1050fc013e28e3852f14923b3a037fa7c5d453a65330'
newhash='425ea5c734c174d0e4e08619d4ed8aebf96e95f60e8a60df9b2fcc010341fb49'
for name in ['write_final_report.py','make_delivery.py','复现与证据说明.md']:
    s=(B/name).read_text(encoding='utf-8').replace('_p3','_p4').replace('ab-p3','ab-p4').replace('P3','P4').replace(oldhash,newhash)
    if name=='write_final_report.py':
        # P3 was stopped during routing and has no final physical comparison.
        # Keep only versions with completed native final timing reports.
        s=s.replace("['指标','R0','P1','P4']","['指标']+list(versions)").replace("['PNR资源','R0','P1','P4']","['PNR资源']+list(versions)")
        s=s.replace('从P1出发，只删除last_use更新循环外层冗余的alloc/DONE/touch全局条件。逐槽条件、写入优先级、沿前退休读取、时间戳不复位、mask维护、查找完成周期保持。core/map/bilinear、DDR、24KiB缓存、FIFO512、lookahead256和FDC/IP未改。P2并行译码未沿用。',
                    '从P3出发，在已有Q_SELECT拍记录行相等/段相等两个标志，Q_CHECK按四分支选择qid，保持原循环较大先前k优先级。沿用P3的时间戳冗余条件删除。没有新增状态或完成拍；时间戳优先级、不复位、沿前退休读取、mask维护均保持。core/map/bilinear、DDR、24KiB缓存、FIFO512、lookahead256和FDC/IP未改。P2并行192槽译码未沿用。')
        s=s.replace('五种故障注入全部被检出。','七种故障注入全部被检出，包含本轮新增行/段相等标志错误。')
    (R/name).write_text(s,encoding='utf-8')
print('P4 report/packaging helpers prepared; no report acceptance or delivery created')
