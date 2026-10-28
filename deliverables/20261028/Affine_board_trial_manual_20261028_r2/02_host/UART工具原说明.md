# FPGA 畸变校正 UART 参数工具 V1.0

命令行工具 `uart_tool.py` 按协议 V1.2 构造并发送 0x01–0x05 命令。
Python 3.8+；唯一第三方依赖是 pyserial。无硬件 `selftest` 只用标准库，
没有安装 pyserial 时也能运行。这里没有修改 FPGA RTL 或已有工程。

## 安装与自测

```powershell
python -m pip install pyserial
# 或: python -m pip install -r requirements.txt
python uart_tool.py selftest
```

自测输出 `[U0]`–`[U5] PASS` 与 `=== ALL TESTS PASSED ===`，非零退出码
表示失败。先用 `python uart_tool.py list` 枚举串口；Windows 串口名称如
`COM3`。所有串口命令统一使用 **115200、8-N-1、无流控、1.5秒接收/写入
超时**。发送前回显完整帧十六进制；串口打不开、短写、回读超时、长度或
校验和错误会给出中文错误和非零退出码。

## 常用命令

```powershell
python uart_tool.py list
python uart_tool.py send-0x01 --port COM3 --params "fx=1000,fy=1000,cx=960,cy=540,k1=-0.1"
python uart_tool.py send-0x02 --port COM3 --affine "a11=1,a12=0,a21=0,a22=1,tx=40,ty=0" --en 1
python uart_tool.py send-0x03 --port COM3 --preset identity --channel all
python uart_tool.py send-0x03 --port COM3 --preset gamma2.2 --channel all
python uart_tool.py send-0x03 --port COM3 --file lut_r.txt --channel 0
python uart_tool.py send-0x03 --port COM3 --file lut_r.bin --channel 0
python uart_tool.py send-0x04 --port COM3 --gamma-en 1
python uart_tool.py read-0x05 --port COM3
python uart_tool.py read-0x05 --port COM3 --status-map status_map.json
python uart_tool.py send-file --port COM3 --csv params_template.csv
```

`send-0x01` 必填 `fx/fy/cx/cy`，其余四项缺省 0；`send-0x02` 的六项
缺省全 0、`--en` 缺省 0。`--channel all` 依序发送 R/G/B 三帧；文件
模式下同一个 LUT 用于三个通道。`.bin` 自动按 256 字节二进制读取，
其他扩展名默认按 UTF-8 文本读取；扩展名不符时使用
`--format text|binary`。文本需恰好 256 个数据行，每行一个 0–255
十进制值，可在值后加 `#` 注释，也可有空行和纯注释行。

恒等 LUT 的前16值是 `0,1,...,15`；幂律预设按
`round(255*(i/255)**2.2)` 计算，前16值为
`0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1`。

## CSV 参数集

`params_template.csv` 的表头顺序固定：

```text
fx,fy,cx,cy,k1,k2,p1,p2,a11,a12,a21,a22,tx,ty,aff_en,gamma_en
```

可以有多行参数集及以 `#` 开头的注释行。工具先检查整个文件、参数
范围和所有将发送的帧，合格后逐行依次发 **0x01→0x02→0x04**。
每帧在主机侧检验字段/长度/校验和，串口写入并 flush 后才发送下一帧。
协议没有这三个命令的 ACK；“发送成功”不等于 FPGA 已应用。不同
命令帧也不是跨帧原子事务，参数组生效时机由 FPGA 帧间隙决定。

默认按 G02 范围（含端点）拒绝越界参数，错误会指出参数名。
`send-0x01`、`send-0x02` 和 `send-file` 可加 `--force` 跳过 G02
预检，发送回显带 `FORCED/OVERRIDE`。该选项不能绕过有符号32位
Q16.16 的编码极限，也不能保证 FPGA 接受越界组。

## 演示建议

1. 运行 `list`，确认板子串口号。先用 `send-0x03 --preset identity --channel all`
   加载恒等 LUT，再用 `send-file` 下发合法参数集。
2. 用 `read-0x05` 记录状态十六进制和无符号十进制；切换
   `gamma2.2`、`--gamma-en 1` 观察效果，再恢复恒等 LUT。
3. 演示范围拒绝时，对同一参数集加 `--force` 发送越界值，再读取状态。
   按冻结确认书和T_LIM通知，非法组仍会切换为现行组，valid=0使引擎
   停止启动新帧；应结合多次状态回读观测，不能仅凭发送日志判断生效。

可选 `--status-map path.json` 解码状态位域；不指定时只输出原始状态字。
2026-10-18 已接入设计方提供的 `status_map.json` 1.2.1（原样保存，依据确认书V1.1）：
bits[7:0] 为 fw_version、bit8 为 params_valid、bit9 为 frame_busy、
bits[15:10] 保留（依冻结确认书不解析/不单列显示）、bits[31:16] 为 pub_count。
新列表格式示例：

```json
{"fields": [{"name": "fw_version", "bits": "[7:0]"}, {"name": "params_valid", "bits": "[8]"}]}
```

仍兼容原字典格式（以下仅为格式示例）：

```json
{"fields": {"example_flag": {"bit": 0}, "example_byte": {"lsb": 8, "width": 8}}}
```

## 协议差异与验证边界

- 任务书冻结向量 V2 与权威协议相冲突：V2 原文有39字节，负载实际34B，
  末尾校验为 B8；协议规定 0x01 负载32B，按所列参数生成37字节整帧，
  正确校验为 **B7**。设计方已确认该勘误，U0 以37B/B7为判据。此次
  确认消息中的粘贴十六进制串仍多了3个零字节；按“32B负载、37B
  整帧”及具体参数布局生成的规范字节串见 `docs/V2勘误确认记录.md`。
  原始任务书保留在 `reference_original`。
- 协议 G02 对 `tx/ty` 允许 ±4096（Q16.16 界 `0x10000000`）。2026-10-18
  设计方通知板端 T_LIM 已修复；工具已移除历史 ±256 警告，±4096 预检不变。
  `reference_original/01_ref` 保留最初收到的历史原件；`reference_current/` 已收录
  修复后RTL、TB、确认书V1.1及映射1.2.1，四件均与补发清单哈希匹配，详见
  `reference_current/基线状态.json`。不要用历史原件覆盖已修复的板端版本。
- `selftest` 是无硬件内存串口验证；本机没有安装 pyserial，也未
  连接真实串口或进行板级联调。`verification/selftest_console.log` 是
  本机 Python 3.12 的完整自测输出。后续仍需核对实际板端版本和回读效果。

`docs/自主决策记录表.md` 记录两项规格冲突和无 ACK 的发送语义。

状态在 FPGA 受理 0x05 的时刻锁存。`frame_busy=0` 不表示写出/发布已完成，
发布次数应看 `pub_count`；该计数器按 65536 回绕，30fps 连续发布时约36.4分钟。
映射备注中的 ModelSim 向量来源属于设计方报告，本机仅进行了无硬件解码验证。
确认书V1.1将I6集成验收快照统一为 `0x00080012`（pub=8、busy=0、valid=0）；
旧 `0x00070012` 保留为合法U4构造帧，已不作为当前I6验收快照。

## 交付与完整性

`docs/补发参考件及增量审查接收说明_2026-10-18.md` 说明当前版本与参考件核对结果；
`docs/T_LIM修复接收说明_2026-10-18.md` 保留为收到修复通知时的历史记录；
`docs/status冻结确认接收说明_2026-10-18.md` 说明按冻结确认书完成的更新；
`docs/状态映射接入说明_2026-10-18.md` 保留为此前映射接入记录；
`docs/交付说明_2026-10-16.md` 保留为上一版本的交付记录。
包内 `SHA256SUMS.txt` 提供逐文件哈希；ZIP 同级的 `.zip.sha256` 和
`_verification.json` 分别记录压缩包哈希、源码/交付副本/解压副本的
自测全文及完整性检查结果。`package.py` 可重新打包并完成这些检查。
