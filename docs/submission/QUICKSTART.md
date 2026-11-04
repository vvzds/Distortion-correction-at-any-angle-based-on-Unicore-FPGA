# 下载、运行与复现

## 1. 获取完整工程

最新工程见 [2026-11-04 候选说明](../../deliverables/20261104/README.md)，也可使用仓库中的完整目录和原始 ZIP。该版本尚未上板，且随包路由源码清单对 4 个 RTL 文件有哈希差异；**不要把随包位流当作已验证可烧录版本**。先在 PDS 2022.2-SP6.1 对当前源码完整重建，核对构建输入哈希、约束和新位流 SHA256，再安排板测。

需要复现已有快速板测结果时，使用 `deliverables/20261103/resource_opt_shared32/` 的回退工程和位流。板测结论只适用于其记录的位流 SHA256。

需要克隆仓库时，推荐 Git 的稀疏检出（保留正确工作树的同时跳过大历史包）：

```powershell
git -c core.longpaths=true clone --depth 1 --filter=blob:none --sparse https://github.com/vvzds/Distortion-correction-at-any-angle-based-on-Unicore-FPGA.git fpga
cd fpga
git config core.longpaths true
git sparse-checkout set submission docs/submission deliverables/20261103/resource_opt_shared32 deliverables/20261104
python submission/verify_final_candidate.py
```

## 2. 下载当前位流

1. 硬件：PG2L100H-6 FBG676、CMOS2 OV5640；HDMI 接显示器或采集卡。JTAG 和 USB-UART 是不同接口。
2. PDS 2022.2-SP6.1 打开 `pango_undistort.pds`；顶层为 `hdmi_ddr_ov5640_top`，约束为同目录 `HDMI_DDR3_OV5640_test.fdc`。
3. 若使用 11-03 回退版，在下载器选择 `bitstreams/pango_bno085_quality_keys_resource_opt_pkg676_seed1_20261103.sbit`，核对器件 PG2L100H，下载到 **SRAM**；done bit=1 表示下载结束。若使用 11-04 候选，先完成当前源码的 PDS 完整构建并确认新位流哈希，再下载到 SRAM。两版断电后都需要重新下载。
4. 当前版本的串口运行参数掉电丢失。首次下载后按下一节载入真实标定并应用。

板载 UART：FPGA RX=B24、FPGA TX=C24，115200、8N1；本次电脑为 COM8，换电脑以设备管理器或 `host/control.py ports` 为准。BNO085 接线见[工程原接线表](../../deliverables/20261103/resource_opt_shared32/docs/BNO085初版接线与板测.md)。

## 3. 启动上位机

在完整工程目录执行，电脑需要已安装 Python 3（建议 3.12）：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-board.txt
.venv\Scripts\python.exe host/gui.py
```

选择正确串口，连接后载入 `calibration/ov5640_1080p.json`，设旋转 0°、缩放 1、水平/垂直平移 0、剪切 0，勾选自适应亮度，点“应用到 FPGA”。
需要恢复快速板测状态时：Brown/Gamma 开启、IMU 映射关闭、画质 Host(0,0)、OSD 隐藏。KEY0/Brown 没有独立直接开关状态读回；结合实际画面和现场按键状态确认，不要盲目重复按键。
GUI 的“自动裁边”会在需要时增加缩放；“剪切”是几何 shear，不是裁剪。

命令行也可只应用标定和零角度矩阵：

```powershell
.venv\Scripts\python.exe host/control.py ports
.venv\Scripts\python.exe host/control.py send --port COM8 --angle 0 --zoom 1
.venv\Scripts\python.exe host/control.py status --port COM8
```

GUI、状态工具和视觉稳像会独占同一串口，切换前先断开前一个程序。采集卡在本次电脑的 DirectShow index 为 1，应使用 MJPG 1920×1080@30；默认 YUY2 曾限制到约 10 fps，不能据此判断 FPGA 输出帧率。

## 4. 重新构建（需要时）

在完整工程目录使用本机 PDS 的实际安装路径：

```powershell
.venv\Scripts\python.exe tools/build.py --name submission_seed1 --seed 1 --pds "D:/FPGA PDS/PDS_2022.2-SP6.1-win64"
```

此命令会执行完整编译，耗时取决于电脑；构建名不能与已有目录重复。`source/`、`ipcore/`、约束和初始化数据都要保留。最终核对 `build/pds/submission_seed1/receipt.json` 和原生时序报告。
重建所得位流的字节或时序可能因工具环境变化而不同；先保留新的哈希及报告，再用于新的实板结论。

## 5. 仿真复现（需要时）

完整工程包含既有 ModelSim 运行记录。安装好仿真器后，在工程目录运行：

```powershell
.venv\Scripts\python.exe tools/run_verification.py
```

具体工具发现规则见 `tools/run_sim.py`。原始相机留出照片数据未包含在整理包，依赖它的像质环节会跳过；跳过不能算作测量通过。
