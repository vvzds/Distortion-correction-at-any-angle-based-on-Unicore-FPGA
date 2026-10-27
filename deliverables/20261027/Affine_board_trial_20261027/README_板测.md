# 动态仿射校正子系统：首次板测包（2026-10-27）

交付状态：**可开始 SRAM 板测的候选包**。包含上位机程序、完整 PDS 输入工程、现有 C50 seed7 位流、真实标定参数、最小软件检查结果。物理转动跟踪与整机闭环仍待本次板测确认。

## 1. 接线与下载

1. 整包解压到本地可写的英文路径，例如 `D:\Affine_board_trial_20261027`。后续命令均在该文件夹运行。
2. 使用与 C50 一致的 PG2L100H-6FBG676 板卡、OV5640、DDR3 及原有接线。不同板卡不能直接使用此位流。
3. 连接板卡电源与 JTAG，PDS 下载器选择 **SRAM**，下载 `01_fpga\bitstream\hdmi_ddr_ov5640_top.sbit`。本轮不需要重编译或写 Flash。
4. 板载 USB-UART 接电脑；板卡 HDMI 输出接采集卡，采集卡 USB 接电脑。HDMI 显示器也可用于先观察固定变换。
5. 使用 Python 3.10+；在未安装依赖的电脑先执行：

```powershell
python -m pip install -r .\02_host\requirements.txt
```

本机已用 Python 3.12.10、NumPy 2.5.4、OpenCV 5.0.0、pyserial 3.5 运行最小检查。需使用带 GUI 的 `opencv-python`，避免用 headless 版本覆盖。

位流 SHA256：`FF98EB4F5F8C0B47DB29F7FE318400441EF64585A500D783C63360799A830565`。首次下载后参数尚未加载，可能黑屏，先执行下述 `init`。

## 2. 最短操作顺序

先枚举 UART，再把后文的 **COM11 替换为本机实际板载串口**。摄像头编号可能为 0、1、2，不能误选笔记本内置摄像头。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode list
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode init -Port COM11
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode preview -Camera 0
```

`init` 加载 `03_params\real_parameters.csv` 中的真实 Brown4 标定参数，关闭仿射与 Gamma，并检查状态版本、参数有效及发布计数前进。预览必须显示采集卡的 **1920×1080** 实时画面；窗口为便于观察缩小显示，估计仍按原始像素坐标进行。不满足分辨率时会停止。Q 退出预览。

先做固定指令实验：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode demo -Port COM11
```

`demo` 自动初始化，然后依次发送恒等、中心旋转 +5°、-5°、X 采样平移 +40 像素，每项至少 2 秒，正常结束发送关闭仿射指令。请从 HDMI 显示器观察，或保留另一个仅运行 `preview` 的窗口。这些名称表示**采样映射**，因此平移采样 +40 时物体通常向画面左侧移动。

确认固定指令能明显改变画面后，关闭独立预览窗口，再启动反馈跟踪：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode track -Port COM11 -Camera 0
```

相机与图案先保持静止，等待终端显示 `Reference captured`。选择纹理丰富、光照稳定的静止平面场景，先缓慢绕镜头轴旋转约 ±5°，每次停住 1～2 秒，观察画面是否逐渐回到参考姿态。固定变换无效果或运动方向加剧时立即按 D，保留日志，停止该项实验。

| 按键 | 跟踪窗口中的作用 |
| --- | --- |
| R | 发送关闭仿射，等待后重新记录当前画面作为参考 |
| D | 发送关闭仿射并暂停跟踪；R 恢复 |
| S | 保存当前采集卡原始截图 |
| Q | 正常退出并发送关闭仿射 |

低置信度或不合理缩放会关闭仿射，进入 `DEGRADED` 等待 R；串口、状态或采集异常则停发并退出。异常退出时 FPGA 可能仍保持最后一组参数；连接恢复后先执行 `init` 或 `reset`。正常退出的关闭指令也没有板端 ACK。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode reset -Port COM11
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode status -Port COM11
```

`reset` 只关闭仿射，不重新加载标定。断电或重新下载位流后必须重新 `init`；`track`、`demo` 已包含初始化。串口以 115200、8N1、无流控工作，不要同时运行其他占用同一串口的程序。

若需指定 Python，给上述任一命令增加 `-PythonExe "C:\完整路径\python.exe"`。若反馈仍明显滞后，可先增大 `-Settle 1.0`，降低移动速度；默认 `-Settle 0.5 -Gain 0.5 -Scale 0.25`。等待时间只用于减少旧帧反馈，不代表收到参数生效确认。

## 3. 本轮应看到什么、记录什么

首次板测只需完成三步：初始化后有实时畸变校正画面；固定指令能造成对应旋转/平移；缓慢转动相机后，开启跟踪的残余倾斜小于关闭时。用 S 分别保存原位、关闭跟踪且倾斜、开启跟踪并稳定后的截图，最好用外部录像同时拍到相机实物转动及显示器画面。可填写 `板测记录.md`，连同对应 `sessions` 子目录回传。

每次运行会在 `sessions\时间戳` 保存 `events.jsonl`，记录命令字节、发送结果、状态、估计矩阵和异常。跟踪还会保存参考图、退出图及退化图。`0x05` 的 valid/busy/pub 只能说明参数组合法及引擎活动，**无法回读实际仿射矩阵，不能单凭它宣称参数已生效**；需结合固定指令造成的可见变化判断。

## 4. 功能边界

- 当前交付是 **PC 从 HDMI 估计二维变化 → UART 0x02 → FPGA 按帧切换并执行映射**；未增加 IMU。
- 默认两次下发至少间隔 0.5 秒，实际更慢，适合慢速转动、停住后观察回正。不能保证相机快速晃动时画面不动。
- 先测 ±5°，再视实板效果扩大角度。俯仰、左右转头、近远景视差、运动物体、模糊、黑边与裁切不可能由此二维仿射环路全部消除。
- 参数来自已有摄像头实采标定；镜头、焦距、模组或分辨率改变后，应重新标定。
- 复用位流此前有实时畸变校正画面证据，相关观测是在仿射/Gamma 关闭时取得。当前动态入口是新增集成，尚未实板签收。48 次/秒发布计数不能视作独立视频帧率，30 个不同画面/秒也未签收。

## 5. 工程与检查

PDS 工程入口为 `01_fpga\run_host.pds`，源文件、IP、约束均在包内，目标为 PG2L100H-6FBG676。C50 位流原构建工具是 PDS 2022.2-SP6.1，seed7；保留已有时序与资源报告供追溯。本轮不重复综合、布局布线、全量回归、长时间和物理转动验收。

若后续改 FPGA：在 `01_fpga` 目录打开工程并重新运行流程；原 `run_host.tcl` 只到 PNR/时序报告，**不生成位流**，仍需在 PDS 中执行 Generate Bitstream。不要把复用位流当作修改后代码的新构建结果。既有 IP 曾有 FBG484 元数据与 FBG676 目标不一致警告，移植或重新生成 IP 时再复核；本轮保持原 IP。

发包前已执行 UART U0–U5、实际采样方向/矩阵复合、坐标转换/Q16、状态解析/短写、参数编码及工程依赖/哈希检查，结果在 `05_checks`。如有必要自行重跑软件检查：

```powershell
python .\verify_package.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode selftest
```

`selftest` 不连接硬件，结果另存到 `sessions`。`04_reference` 和 `02_host\reference_original` 为历史材料，保留其中原路径和原文；实际启动以本说明及 `board_trial.py` 为准。原 `affine_track.py` 保留作为估计器来源，**不要直接启动旧脚本进行本次闭环**。
