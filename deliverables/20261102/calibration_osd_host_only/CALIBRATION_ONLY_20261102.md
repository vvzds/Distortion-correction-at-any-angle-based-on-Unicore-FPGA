# 标定参数专用 HDMI 显示工程

本工程直接由用户提供的 `pango_1080p30_HDMI_OSD_candidate_final_20261031.zip` 解压建立。保留其 RTL、IP、PDS 工程、约束和 `release/osd_candidate_seed3_20261031.sbit` 原样；没有重新综合、布线或修改校正算法。原压缩包 SHA256 为 `0ca1badcc2961d6e4f0ff25c8cdd0d21a9b9cb71a3ac65400093e9319826bf05`，位流 SHA256 为 `f0917534a99df79905aba11331fd44e46ad2166c82216332f585727b81da6b66`。

## HDMI 显示

只有以下四行文字，取自 `calibration/ov5640_1080p.json`：

```text
FX=1507.7104 FY=1507.4035
CX=883.5331 CY=568.6877
K1=-0.381483 K2=+0.156698
P1=-0.000303 P2=-0.000111
```

上位机每次开启叠层时还会向原位流的第 4 至第 7 行写入空格，清除原有 FPS、画质、状态等文字。后续状态轮询和图卡测量不会再向 HDMI 写入这些数据；电脑端仍可查看测量结果。原位流的 8 行高深色背景框仍在，不能仅靠上位机软件缩小；若必须让背景框也缩成 4 行，就需要修改 RTL 并重新布线生成位流。

这些数字是**上位机标定文件解析值，不是 FPGA 配置寄存器回读值**。上位机可以解析 `fx/fy/cx/cy` 和 `k1/k2/p1/p2`，但若板端加载了另一套参数，屏显不能单独证明板端实际使用的是这一套。

## 使用

1. 将 `release/osd_candidate_seed3_20261031.sbit` 下载到 FPGA SRAM。此步骤与原包相同，不写 Flash。
2. FPGA 控制串口连接电脑后，在本目录执行 `python host/osd_monitor.py --port COMx`；把 `COMx` 换成实际端口。也可运行 `python host/gui.py`，连接串口后打开“HDMI参数叠层”。两者不可同时占用串口。
3. 如使用另一份标定文件，独立脚本传 `--calibration PATH`；GUI 中载入标定后，需要应用配置并重新打开叠层。

原包 `requirements.txt` 提供 Python 依赖。离线检查执行 `python tools/check_osd_host.py`，预览执行 `python tools/render_osd_preview.py`。检查已验证 8 条 OSD 行命令及空行内容、CRC 封包和原位流 SHA256；本次没有连接板卡，实际屏显与 30 fps 均未重新板测。原包的 PDS 报告和历史板测结论不能自动充当本次上位机改版的板上验收。
