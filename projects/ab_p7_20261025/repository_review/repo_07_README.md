# 静态校正已出图，真实新帧率待优化

制作：二号协作者；接收：执行者/管理方，以及一号协作者（整机链路）。

## 已完成

本包对应用户实际烧录并确认“矫正成功”的源码、位流、原生时序和UART记录。起初串口连续回复0x00000012：参数无效、引擎空闲、发布计数0。上电默认读取校正槽，未下发参数时没有已发布校正帧，所以显示屏锁定1080P30仍黑屏。先下发恒等参数恢复基准画面，再下发既有真实Brown4参数；参数有效且发布计数递增。

## 必须保留的限制

真实参数稳定窗口 10.266s 新发布 40帧，约 3.896fps，未达到校正新帧30fps目标。HDMI时序仍是1080P30，会重复显示已有校正帧。本包是可出图候选，不能标作性能终验通过。仍需新帧率优化、画质截图/定量验收。原生时序All Constraints Met、slow setup WNS +0.183ns；外部端口约束覆盖警告仍在。

## 下载与上电

1. 管理方核对VERSION.json和SHA256SUMS.json；实际位流位于 `01_project/generate_bitstream/hdmi_ddr_ov5640_top.sbit`，SHA256为 `67ce6939f03abe9e9594f6bd071a567988eeda96fecb4eec2c3f5b8ed6cdf317`。这是本次实测新位流，不能与旧3084...位流混作同一证据。
2. PDS/Fabric Configuration执行普通SRAM配置，核对器件PG2L100H；保持HDMI和板载USB-UART连接。完整工程入口 `01_project/full_source_top_recovered.pds`，含原样源码/IP/FDC及本轮全部原生构建产物。
3. 每次重新下载或断电重启后运行 `04_uart_tool/run_real_parameters.cmd`；程序定位CP2102，先核对0x12固件，再发送关闭Gamma、关闭仿射、真实参数，并回读params_valid/pub_count。仅发送无ACK的报文不算参数已应用。基准对比使用run_identity_parameters.cmd；恒等映射保留原始镜头畸变。

工具依赖pyserial。本机沿用既有host_validation_deps；其他电脑需使用已有Python并安装requirements.txt，运行 `python apply_parameters.py --real`。本包不含Python/PDS安装包。COM11是本次CP2102枚举结果；工具按VID/PID定位，不能使用JTAG的COM9/COM10。

## 版本与下一步

本包保留源码、真实/恒等参数、全部报告与原始串口回读。由于真实校正新帧率尚不达标，不据此删除仍有价值的历史候选或验收证据。下一步由二号针对真实映射的源行缓存和DDR读访问开销定位性能；执行者/管理方记录实机视觉确认与性能缺口；一号保留采集/显示接口契约。
