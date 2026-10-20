# 上位机工作包部署与标定操作指南（二号 PC）

版本 V1.0 / 2026-10-18。本包把二号 PC 配置为图像畸变校正系统的**上位机**，
承担三项职责：UART 参数下发与状态回读、相机标定（生成基准畸变参数）、
矫正效果评估（MTF50 / 直线度）。RTL 与板级无需任何改动。

## 0. 包内容清单

| 路径 | 内容 |
|---|---|
| UART_HOST_TOOL/ | 参数下发工具 V1.0（已验收交付版，18 文件原样） |
| calibration_tools/ | 标定与质量分析脚本 capture.py / calibrate.py / mtf50.py / linearity.py |
| docs/UART参数协议规格_V1.2.md | 帧格式权威（0x01-0x05、Q16.16 定点、checksum） |
| docs/status位域冻结确认书_20261015.md | status 32bit 位域语义（V1.1） |
| docs/status_map.json | 位域 JSON 映射（1.2.1，read-0x05 可选解码用） |
| README_HOST_PC.md | 本指南 |

## 1. 环境安装（可整段交给 codex 执行）

> 安装 Python 3.10+（无则 `winget install -e --id Python.Python.3.12`），
> 用国内镜像安装依赖 `opencv-python numpy pyserial`，然后在 UART_HOST_TOOL
> 目录运行 `python uart_tool.py selftest`，应 U0-U5 全 PASS、退出码 0
> （无需硬件）。若 PATH 未刷新用 python 绝对路径调用。

```powershell
python -m pip install opencv-python numpy pyserial -i https://pypi.tuna.tsinghua.edu.cn/simple
cd UART_HOST_TOOL
python uart_tool.py selftest
```

HDMI 采集卡（MS2109/MS2130 类）USB 免驱直插，设备管理器出现"USB Video"
设备即可，无额外驱动步骤。

## 2. 硬件接线

- **视频**：整机 HDMI 输出 → 采集卡 → PC USB。PC 侧必须确认采集到
  **1920x1080 原始分辨率直通**——任何缩放抓帧都会使标定坐标系与引擎
  输出坐标系不一致，标定结果作废。capture.py 启动时会自动检查并告警。
- **串口**：板级 USB-TTL → PC COM 口，115200-8N1（协议 V1.2 冻结值）。

## 3. 相机标定 SOP

### 3.1 采集（capture.py）

```powershell
cd calibration_tools
python capture.py          # 打不开设备则 --cam 1 试序号；空格存帧到 calib\，q 退出
```

摆拍 **≥20 张**：
- 距离分 3~4 档（约 30 / 45 / 60 / 80 cm）；
- 每张至少一个姿态变化：俯仰、偏航 ±15°~±40°，可加小翻滚；
- 棋盘分别移到画面**左上 / 右上 / 左下 / 右下 / 中心**，每区 ≥2 张
  （边角是畸变信息的主要来源）；
- 每张自查：棋盘完整入画、清晰无运动模糊、无反光过曝。

标定板为采购 12×9 板、方格 25mm——capture/calibrate 默认值已按此设置，
无需修改参数。

### 3.2 标定（calibrate.py）

```powershell
python calibrate.py         # 自动探测内角点规格（12x9 内点 / 11x8 内点）
```

脚本自动完成：角点探测（两种标称口径自动判定）、4 参数模型标定
（径向 k1,k2 + 切向 p1,p2，与 FPGA 引擎同构、无 k3）、逐张重投影误差、
G02 范围预检、UART 0x01 帧生成，并存档 `calib_result.json`。

**质量门槛**：
- 总 RMS < 0.5 px（目标 < 0.3）；逐张 > 1 px 的文件删除后重跑；
- fx/fy 互差 < 2%；cx/cy 靠近 (960, 540)；
- G02 预检 8 参数全部在引擎合法域内；
- **|k1| 在 1e-3~1e-2 量级属正常**（OV5640 中心裁切后视场小、原生畸变
  弱），不是标定失败；若越界（|k|>0.5、|p|>0.01）优先排查标定板平整度、
  摆姿角覆盖是否单一、反光。

## 4. 参数下发与验证闭环（UART_HOST_TOOL）

```powershell
python uart_tool.py list                                # 确认 COM 口号
python uart_tool.py send-0x03 --port COMx --preset identity --channel all   # 先恒等 LUT 校验链路
python uart_tool.py send-0x01 --port COMx --params "fx=...,fy=...,cx=...,cy=...,k1=...,k2=...,p1=...,p2=..."
python uart_tool.py read-0x05 --port COMx --status-map ..\docs\status_map.json
```

- 0x01 数值直接抄 `calib_result.json`（工具自动做 G02 预检与 checksum，
  参数 key 名以 `uart_tool.py --help` 为准）；
- `read-0x05` 判据：**params_valid (bit8) = 1**；引擎运行时 pub_count
  递增。若 bit8=0 说明参数越界被引擎拒收（对照 G02 范围检查标定值）；
- 最后实拍对比矫正前后画面（矫正后画面应无可见变化——因为本相机
  原生畸变极小，矫正的意义在于参数链路全通、引擎按真实标定参数运行）。

## 5. 矫正效果评估（矫正参数生效后复测）

- **直线度**：`python linearity.py IMG.png --minlen 300`
  图卡：网格线 / 倾斜黑色方块。判据：矫正后 max 偏差 ≤ 1~2 px、
  边缘无断裂/拉伸（赛题判据）。
- **MTF50**：`python mtf50.py IMG.png --roi x y w h`
  图卡：SFR 斜边卡（刃倾角 5~15°）；ROI 框住刃及其两侧渐变带各 ≥40px，
  ROI 内不得含其他边缘。同卡同 ROI 矫正前后各测一次，输出 cy/px 与
  `mtf_curve.csv` 对比。

## 6. 板级演示用例（预案）

- **越界拒绝演示**（阶段 4 "参数越界拒绝启动"）：对同参数组把 fx 改成
  64 加 `--force` 发送，`read-0x05` 应见 valid=0、引擎停机（G02 拒绝启动）。
- **Gamma**：`send-0x03 --preset gamma2.2 --channel all` +
  `send-0x04 --gamma-en 1`（演示后用 identity 恢复）。
- **任意角度/仿射**（高阶任务演示）：`send-0x02 --affine
  "a11=...,a12=...,a21=...,a22=...,tx=...,ty=..." --en 1`。

## 7. 回传清单（我方审核归档用）

1. `calib_result.json`（标定证据链——赛题要求畸变参数须来自真实标定）；
2. 代表性标定原图 3~5 张（从 calib\ 挑选，含四角位姿）；
3. 矫正前后对比帧各 2~3 张；
4. linearity / mtf50 输出与 mtf_curve.csv；
5. selftest 通过的 console 输出（环境部署证据）。
