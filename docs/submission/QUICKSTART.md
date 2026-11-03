# 下载、运行与复现

## 1. 获取完整工程

优先从 [Release](https://github.com/vvzds/Distortion-correction-at-any-angle-based-on-Unicore-FPGA/releases/tag/competition-1080p30-20261104) 下载比赛整理包，避免下载仓库中数 GB 的历史归档。
解压到较短英文路径（如 `D:\fpga_submit`），其中 `project/pango_undistort.pds` 是 PDS 工程。
如直接使用 GitHub 文件树，对应路径是 `deliverables/20261103/resource_opt_shared32/pango_undistort.pds`。

需要克隆仓库时，推荐 Git 的稀疏检出（保留正确工作树的同时跳过大历史包）：

```powershell
git -c core.longpaths=true clone --depth 1 --filter=blob:none --sparse https://github.com/vvzds/Distortion-correction-at-any-angle-based-on-Unicore-FPGA.git fpga
cd fpga
git config core.longpaths true
git sparse-checkout set submission docs/submission deliverables/20261103/resource_opt_shared32
python submission/verify_submission.py
```

## 2. 下载当前位流

1. 硬件：PG2L100H-6 FBG676、CMOS2 OV5640；HDMI 接显示器或采集卡。JTAG 和 USB-UART 是不同接口。
2. PDS 2022.2-SP6.1 打开 `pango_undistort.pds`；顶层为 `hdmi_ddr_ov5640_top`，约束为同目录 `HDMI_DDR3_OV5640_test.fdc`。
3. 在下载器选择 `bitstreams/pango_bno085_quality_keys_resource_opt_pkg676_seed1_20261103.sbit`，核对器件 PG2L100H，下载到 **SRAM**；done bit=1 表示下载结束。该位流断电后需要重新下载。
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
