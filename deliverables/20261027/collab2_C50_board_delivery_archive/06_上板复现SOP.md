# C50 seed7 上板复现 SOP

1. 将整个交付目录解压到英文路径，例如 `D:\FPGA PDS\yx\C50_board_delivery_20261027`。PDS 对中文路径可能失败；不要只拷贝 `.pds` 而丢失同级 `source/`、`ipcore/`、`.fdc`。
2. 板卡供电并连接 JTAG、板载 CP210x USB-UART 和 HDMI。用 PDS 2022.2-SP6.1 打开 `01_PDS_project/run_host.pds`。若仅复现本次板测，无须重新综合；在 Configuration 中选择 `01_PDS_project/bitstream/hdmi_ddr_ov5640_top.sbit`，执行普通 FPGA SRAM Program。成功后保持供电。
3. 在 PowerShell 中进入交付目录，安装 Python 3.8+ 与 `pyserial`（仅首次），查找板载 CP210x 串口；本次板测为 COM11，其他电脑以实际枚举为准：

```powershell
python -m pip install -r .\04_uart_tool\requirements.txt
python .\04_uart_tool\uart_tool.py list
python .\04_uart_tool\uart_tool.py selftest
```

4. 将下列命令中的 `COM11` 改成实际串口，然后下发本次真实参数并读取状态：

```powershell
python .\04_uart_tool\uart_tool.py send-file --port COM11 --csv .\03_runtime_params\real_parameters.csv
python .\04_uart_tool\uart_tool.py read-0x05 --port COM11 --status-map .\04_uart_tool\status_map.json
```

5. 确认状态中 `params_valid=1`，显示器出现实时校正画面；再进行动态测试。初次黑屏若状态为 `0x00000012`，先检查参数是否已下发。若串口无响应，检查 CP210x 驱动、板载 USB-UART 数据线与位流下载；若有状态但 HDMI 无图，检查 DDR 初始化、摄像头供电/连线和 HDMI 输入选择。

注意：下载到 SRAM 不会持久化，断电后需要重新 Program；UART 标定参数也需重新下发。本包没有自动上电参数固化功能。`03_runtime_params/` 中的 `.bin` 是预编码参考帧，通常直接使用 CSV 命令即可。
