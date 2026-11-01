# 四行标定参数 OSD 交付记录

本版将 HDMI 深色背景框从 `x=24..807, y=24..223` 缩至 `x=24..807, y=24..127`。屏幕只绘制四行标定参数；第五行以下透传原视频。UART 的 8 行命令格式保持兼容，上位机仍发送四行参数并清空旧版后四行。采集、Brown4 映射、DDR 与帧发布链路没有改动。

## 位流与验证

- 新位流：`release/osd_calibration_4row_seed3_20261102.sbit`
- SHA256：`936faf1070b57a9aba778b0767a601f3de799b9f708bdaf1f5f4857e5d24467d`
- 设备：PG2L100H-6 FBG676；PDS 2022.2-SP6.1；place/route seed 3。
- PDS 完整实现退出码 0；所有时序约束通过。125 MHz DDR 主域 slow setup WNS +0.484 ns、slow hold WHS +0.142 ns；74.25 MHz HDMI 像素域 slow setup WNS +4.175 ns、slow hold WHS +0.353 ns。
- 资源：LUT 10,198，FF 15,551，APM 60，DRM 84.5。原生报告见 `reports/pds_four_row_seed3/`，含构建回执、源码哈希清单、控制台日志和完整时序报告。
- Icarus Verilog：`video_osd_tb` 与 `host_control_tb` 均 PASS，覆盖第 4 行边框、第 5/8 行原像素透传、UART CRC、边界检查与帧界显隐。
- 上位机离线检查通过：9 条 OSD UART 命令、标定行和离线样本检查。`reports/osd_layout_preview.png` 是软件合成的布局预览，不是实板照片。

尚未将本位流下载到板卡。上述仿真和 PDS 结果**不能证明实际显示或 30 个不同校正画面/秒**；上板时须按 `BOARD_TEST.md` 测量画面与新帧率。旧八行背景位流 `release/osd_candidate_seed3_20261031.sbit` 保留供回退。
