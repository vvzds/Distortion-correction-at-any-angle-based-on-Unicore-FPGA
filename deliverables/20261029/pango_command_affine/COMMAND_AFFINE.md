# 上位机指令驱动的动态仿射校正

本入口使用 `release/pango_undistort_clean_smooth.sbit` 对应的 Clean Smooth v2 协议。
相机采集、Brown4 畸变映射、双线性插值、帧缓存及 HDMI 输出仍由 FPGA 完成；
上位机只发送每帧仿射目标。启动时读取 21h 固件身份，不会误接不含该反馈协议的旧位流。

## 运行

```powershell
python -m pip install -r requirements-board.txt
python host/command_gui.py --port COM9
```

在窗口输入旋转角、缩放、平移、剪切，选择 Slow / Normal / Fast，点击 Apply target。
控制线程以最多 30 次/秒下发最新矩阵。角度是连续输入：例如从 0 输入 270，
会按照 +270 度方向转动，不会自动走 -90 度短弧；输入 -90 则向负方向转。
Slow / Normal / Fast 的最大角速度分别为 45 / 180 / 540 度每秒。
新目标会覆盖尚未完成的旧目标。Reset 恢复 0 度、2 倍固定裁边。
正常断开会恢复 0 度、1 倍静态畸变校正；窗口异常终止来不及执行恢复。

脚本或后续传感器适配器可以通过 JSONL 标准输入发送目标：

```powershell
python host/command_console.py --port COM9 --speed fast
```

每行一个 JSON 对象，例如 `{"angle":90,"zoom":2.0,"shear":0.1}`。
未提供的字段沿用上一目标；`{"command":"status"}` 查看最新目标和发送数，
`{"command":"reset"}` 恢复默认控制目标。输入结束时恢复静态校正并关闭串口。
如果上位机输入是实际相机滚转角，应先标定传感器安装轴向，再换算为显示补偿角；
不能直接把 IMU 原始字节流送进这个 JSON 入口。

## 工程边界

- 默认 2 倍固定裁边面向全角度旋转和适度剪切，避免角度变化时裁边呼吸。
  它会显著缩小视野。每个目标与中间矩阵都经保守 patch 容量检查；
  该检查不能保证任意平移、剪切与缩放组合无黑边。
- FPGA 使用 Brown4 之后再对整帧做仿射采样。输入角度由上位机提供时，
  30 fps 视频最多每 33.3 ms 显示一个新姿态；540 度/秒对应每帧约 18 度。
  速度档只是命令侧上限，不是已测得的相机到屏幕响应速度。
- 此入口默认关闭 FPGA 半距平滑，以免在快速命令上再叠加一层滞后。
  可用 `command_console.py --smooth` 开启它，但需重新比较响应和抖动。
- 仅靠六参数仿射不能完全矫正较大俯仰/偏航造成的透视、近景视差和遮挡。
  剪切是画面近似参数，不能被解释成三维相机姿态角。
- 现有 `host/board_trial.py` 保留画面特征自动稳定；这次新增的是独立的
  外部指令路径。手动指令路径没有用预设正弦曲线伪装为相机姿态。

## 验证与后续板测

```powershell
python tools/check_command_affine.py
python tools/check_stabilizer.py
python tools/check_board_trial.py
```

离线检查覆盖多个小/大角度的生产定点映射、全幅有效率、patch 上界、
速度档、大角度连续推进、新目标覆盖旧目标、固件检查和退出恢复。
上板需要测固定场景与移动标定板的唯一相机帧、唯一校正帧和 HDMI 唯一帧，
并记录角度阶跃/斜坡的跟随延迟、黑边、残余抖动和超调。
交付包原有板测证明 Clean Smooth v2 的校正发布约 30 fps，
不等于本新增快速动态指令路径已经完成实板验收。
