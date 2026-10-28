# 2026-10-28 实板画面更新率对照

## 结论范围

同一台 Hagibis 采集器以 1920x1080 MJPEG 30 fps 接收 HDMI，在镜头前持续移动手或标定板，各录 25 秒：

| SRAM 位流 | SHA256 | 采集帧 | 不同画面切换 | 更新率 | 每秒切换数 |
| --- | --- | ---: | ---: | ---: | --- |
| C50 seed7 `D:\FPGA PDS\yx\C23_core30_20261026\host_c50\generate_bitstream\hdmi_ddr_ov5640_top.sbit` | `FF98EB4F5F8C0B47DB29F7FE318400441EF64585A500D783C63360799A830565` | 751 | 452 | 18.056/s | 完整秒为 18-19 |
| 用户提供的 `D:\FPGA PDS\ww\s_1080p30_.sbit` | `014DDC2B4B834EC5194AAAC5085A7B609A3D43F7FC0A5D8D21A8E49E06EF8547` | 751 | 493 | 19.694/s | 每秒 18-21 |

两次输出画面均未达到稳定的 30 个不同画面/秒。两段运动不是完全相同的机械轨迹。第二个位流在本机和仓库中只找到文件名、哈希和实测，未找到匹配的源码及构建记录；不能据此证明它是与 C50 相同 OV5640 配置的纯原始直通工程，也不能将 19.694/s 当作传感器的输入帧率。

C50 的 UART 状态在装载标定参数前为 `0x00000012`，黑屏；装载仓库 `deliverables/20261026/collab2_C22_seed7_board_trial/reference/parameters/real_parameters.csv` 后参数有效、引擎运行。25.8817247 秒内发布计数增加 1244，即 48.0648 次完整校正帧写回/秒。发布数远高于 HDMI 不同画面更新数，不能代表相机新帧或显示更新数。旧位流无 0x05 状态回复。

## 测量方法与原始记录

- `c50_motion_framehash.txt` 和 `s1080_motion_framehash.txt`：FFmpeg 对每个 Hagibis 采集帧缩放至 320x180 灰度后计算 SHA256。相邻哈希不同才记一次画面切换；缩放灰度会漏掉细微变化，因此这是可见内容更新的保守估计。
- `c50_motion_uart.tsv`：六次 0x05 状态回读，约每五秒一次，保留时间戳和原始状态字。
- `analyze_framehash.py`：逐秒复算、连续相同帧长度与总速率。运行 `python analyze_framehash.py c50_motion_framehash.txt`；第二版改用 `s1080_motion_framehash.txt`。最后一秒只有 1/30 秒的边界采样，不应作为完整的一秒统计。

采集命令的关键参数：`-f dshow -video_size 1920x1080 -framerate 30 -vcodec mjpeg -i video=Hagibis -t 25 -vf scale=320:180,format=gray -f framehash`。采集器能够按 30 fps 交付缓冲帧，但重复帧说明当前可见内容更新不足。COM11 串口和采集器均在运行；SRAM 位流断电后需重新下载，C50 运行参数也需重新发送。

## 下一项硬件诊断

需要在同一个可追溯的工程内，独立计数 OV5640 VSYNC、DDR 原始帧完成、校正完整帧发布、HDMI 垂直消隐时真正换到新校正槽的次数。计数周期、跨时钟同步和状态回读必须可复现，并在相同持续运动场景下测量。优先从仓库已有的 CMOS2 RAW8-视频直通源码重建可追溯基线，先验证并优化采集/缓存/显示，再集成校正引擎。只有各段均满足 30/s 且不丢相机新帧，才能通过用户要求的 1080p30 端到端验收。
