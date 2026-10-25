# 模块10：标定入口与画质证据

二号维护，2026-10-25。M02已签收候选现应用到本仓库`calibration/calibrate.py`，SHA256为`e7581eedb1b62090eef15d0d083eb58b41f21b1965438613c45acc2fa7862ebe`。这是仓库入口应用；不代表其他电脑、历史工程包或快捷方式都已经切换。

与原仓库脚本相比，沿用已审验的1920×1080图像过滤、显式固定k3=0的Brown4模型、G02失败诊断、量化往返和量化后范围检查，以及在`python -O`下仍有效的异常检查。UART协议与既有真实标定参数不变。原仓库文件保存在本轮交付包的`history/`及Git父提交中。

## 标定运行

使用已有Python 3.10+、NumPy、OpenCV。本机棋盘是12×9格、11×8内角点、25mm；不要把格数直接作为内角点数。

```powershell
python calibration/run_calibration.py --images D:/calib_input --out D:/calib_runs/new_run --cb 11 8 --square-m 0.025 --scratch D:/calib_scratch
python calibration/run_calibration.py --verify D:/calib_runs/new_run/receipt.json
```

输入文件是平铺PNG/BMP；输入、输出和scratch三个目录必须分开。输出路径必须不存在。图片目录有中文时，启动器将原图暂存到ASCII scratch子目录并核对逐张SHA；文件名本身使用ASCII。暂存不修改原图，暂存目录留到归档后再清理。OpenCV旧版在Windows直接读取中文路径可能失败，推荐始终通过本启动器调用。

`VALIDATED_OFFLINE`只表示本次生产进程成功、G02和独立37字节帧校验通过。新目录中的`receipt.json`记录源码/输入/输出SHA、命令、PID、时间和退出码；只有成功运行才生成`validated_uart01.hex`。失败保留日志和诊断，不复用旧成功目录。`--verify`还要求原始源码及输入文件仍在原路径，移机后应依据清单重新运行，不编辑旧回执使其伪装通过。

启动器不打开串口、不发送参数，也不代表标定精度或板端验收。发送前由现用UART工具按冻结协议核对，不能只凭历史`calib_result.json`或`params_valid=1`认定实际画面已应用。本轮没有覆盖现有真实参数文件。

## M03画质评价

正式M03批处理工具、schema、原MTF E8/直线度工具和复验脚本随本轮交付包保存。实图应来自采集卡原分辨率抓帧，保留传输格式；屏摄和软件重映射图片不能作为FPGA输出原帧。

静态画质拍摄允许使用当前约4fps校正新帧率，但每次切换后需核对发布计数前进并清空视频队列；这不豁免帧率指标。固定机位/图卡，记录曝光、白平衡、焦点、Gamma/仿射状态；自动控制或采样比例变化时，分别给出单侧测量和比较限制。MTF/SFR需要适当的斜边ROI，同一坐标不等于同一物理刃，棋盘角点直线度不等于MTF。

所有质量判据仍由执行者/管理方按赛题确认，工具不能自行把软件通过提升成整机质量通过。
