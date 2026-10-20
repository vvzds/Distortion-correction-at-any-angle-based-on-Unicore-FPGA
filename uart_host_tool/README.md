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
   FPGA 可能静默拒绝；状态位的具体语义需顶层确认，不能仅凭发送日志
   判断是否生效。

可选 `--status-map path.json` 解码设计方将来提供的状态位域；工具不
依赖该文件。映射格式示例（以下名称和位号只是格式示例，并非已冻结的
实际状态定义）：

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
- 协议 G02 对 `tx/ty` 允许 ±4096（Q16.16 界 `0x10000000`），但任务包
  的 `param_mgr.v` 当前 `T_LIM=0x01000000`，即 ±256。工具遵守协议
  范围，对绝对值超过256的 tx/ty 额外报警但仍允许发送。板端若未
  修订，会拒绝这类参数组。
- `selftest` 是无硬件内存串口验证；本机没有安装 pyserial，也未
  连接真实串口或进行板级联调。`verification/selftest_console.log` 是
  本机 Python 3.12 的完整自测输出。设计方仍需核对 `tx/ty` 范围差异
  及后续板级回读效果。

`docs/自主决策记录表.md` 记录两项规格冲突和无 ACK 的发送语义。

## 交付与完整性

`docs/交付说明_2026-10-16.md` 说明最终交付内容与验证方式。
包内 `SHA256SUMS.txt` 提供逐文件哈希；ZIP 同级的 `.zip.sha256` 和
`_verification.json` 分别记录压缩包哈希、源码/交付副本/解压副本的
自测全文及完整性检查结果。`package.py` 可重新打包并完成这些检查。
