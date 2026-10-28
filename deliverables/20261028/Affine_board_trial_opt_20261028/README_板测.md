# 动态仿射性能优化板测包（2026-10-28）

本版继续优化上位机状态机、图像估计和交互。FPGA RTL、IP、约束及 seed7 位流不变。此前小角度实板跟踪证据仍成立；本包的新估计器和控制策略尚未物理板测，性能收益需现场复核。

## 1. 接线与下载

解压至可写的英文路径，连接与上一版相同的 PG2L100H-6FBG676、OV5640、DDR3、JTAG、CP210x UART 和 HDMI 采集卡。不同板卡不能直接使用此位流。首次上电用 PDS 下载器选 SRAM，下载 `01_fpga\bitstream\hdmi_ddr_ov5640_top.sbit`，不需要重新编译或写 Flash。断电/下载后重新运行 init。

位流 SHA256：`FF98EB4F5F8C0B47DB29F7FE318400441EF64585A500D783C63360799A830565`。

使用 Python 3.10+，依赖安装命令：

```powershell
python -m pip install -r .\02_host\requirements.txt
```

使用带 GUI 的 opencv-python，不能用 headless 代替。脚本支持 `-PythonExe "C:\完整路径\python.exe"`。

## 2. 最短操作顺序

在解压目录运行；COM11 和 Camera 0 换成本机实际串口与 HDMI 采集卡编号，不能选笔记本内置摄像头。采集帧须为 1920×1080。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode selftest
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode list
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode init -Port COM11
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode preview -Camera 0
```

Q 退出预览。init 下发已有真实标定参数并关闭仿射/Gamma，检查参数有效与发布进度。首次下载后参数尚未加载可能黑屏。标定参数仅适用于原镜头与分辨率，换镜头需要重新标定。

先用 HDMI 显示器或独立 preview 窗口观察固定指令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode demo -Port COM11
```

demo 自动初始化并依次发恒等、采样旋转 +5°/-5°、X采样+40像素，正常结束关闭仿射。采样方向与画面物体运动方向不同；X采样+40时物体通常向左移动。

确认固定指令正常后关闭独立 preview，先用保守跟踪档，再试默认档；两条命令分别运行，不要同时占用串口/采集卡：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode track -Port COM11 -Camera 0 -Settle 0.25 -Gain 0.4
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode track -Port COM11 -Camera 0
```

相机先保持静止，等待 Reference captured 后再移动。默认参数：Settle 0.15秒、Gain 0.6、每步旋转1.25°、中心平移40px、命令角点位移60px、估计预算0.25秒、PC解码帧最大年龄0.45秒、HOLD超时2.5秒。时间预算不是矩阵应用ACK，解码时间也不是曝光时间。

| 按键 | 功能 |
| --- | --- |
| R | 关闭当前仿射并建立新的参考；不会回到旧参考姿态 |
| D | 关闭仿射并暂停跟踪 |
| S | 保存当前原始 HDMI 采集帧 |
| Q | 正常退出并发送关闭仿射 |

发生通信/程序错误时会停发，FPGA可能保持最后一组参数；恢复连接后执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\run_board.ps1 -Mode init -Port COM11
```

reset 模式只关闭仿射，不重新加载标定。正常关闭指令也没有矩阵 ACK。

## 3. 本版优化

- HOLD 新增2.5秒超时；有效观察打断连续失败计数，不再把隔着有效帧的故障误算为连续故障。连续3个坏观察或HOLD超时会关闭仿射；恢复需要连续2个置信度至少0.75的有效观察。
- 新估计器缓存参考特征和图像金字塔，使用双向一致特征匹配、RANSAC、内点率、空间覆盖、重投影误差、原始矩阵几何及有效重叠检查。先检查原始估计，再限制步长。
- 单独估计线程运行多尺度恢复；不排队旧图。人工D/R/Q会使在途结果失效，过期结果不得写串口。串口只由主线程管理。
- 极分解和图像中心步进代替矩阵线性混合，纯旋转保持单位尺度；最终命令的每步角点位移另行限制。
- 周期0x05采用增量非等待接收，保留状态版本、参数有效和发布停滞检查，避免等待完整回复时冻结GUI。真实设备写入/flush仍可能受驱动超时影响，不能承诺硬实时按键响应。
- 每次参考独立保存为 reference_001.png、reference_002.png；日志增加估计起止、解码帧龄、质量和丢弃原因。

## 4. 板测和调参

先用静止、非重复、细节丰富的平面图案，依次测 ±1°、±3°、±5°，每次停稳；再单独试平移。记录首个可见补偿时间、停住后的收敛时间、过冲/振荡、HOLD原因及恢复时间。最好用外部录像同时拍相机运动和直连HDMI显示。采集卡预览可能有附加延迟。

若来回抖动，D后改用0.25/0.4；若HOLD频繁，先改善纹理、照明和曝光，再看日志拒绝原因。不要直接降低EccMin或删除几何保护。若CPU较慢导致预算/帧龄频繁超限，可试 `-EstimateBudget 0.4 -MaxFrameAge 0.65`，代价是容许更旧的观察。

首次CPU/特征缓存冷启动可能较慢，首个结果可能按预算被丢弃；相机保持静止时应随后恢复。如超过HOLD期限，则在静止后R重锚。

需要扩大范围时，先确认稳定，再逐步增加MaxRotStep或MaxShiftStep。累计20°/800px为试验安全包络，并非已验收能力。黑边、裁切、模糊、视差和3D透视变化无法由本二维仿射闭环全部消除。

## 5. 文件与验证边界

每次运行在sessions目录生成日志，填写板测记录.md并回传对应会话。0x05的valid/pub只能说明合法性与处理活动，不能证明矩阵已经在HDMI显示；发布计数不等于独立视频帧率。

05_checks包含UART U0-U5、闭环/方向、超时与连续计数、几何质量、±12°合成估计、缓存/预算、过期帧、worker取消、慢估计时人工控制、分段状态回复等软件结果。saved_image_replay.json仅是开发PC对历史截图的离线回放，不是实体板性能测量。

验证包：`python .\verify_package.py`。该命令核对文件哈希、PDS输入和原位流，不运行PDS。工程入口仍为01_fpga/run_host.pds；原run_host.tcl只到PNR与报告，重建时还需在PDS执行Generate Bitstream。工具版本和IP封装元数据的历史限制见04_reference。

04_reference中的20261027文件为历史材料，当前实现以本说明和本次优化与限制.md为准。尚无IMU、光流预测或矩阵应用帧标识，也未重新验收独立帧率、大角度或快速防抖。
