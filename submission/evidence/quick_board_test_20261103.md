# 最终功能快速板测回执

日期：2026-11-03T11:43:34.321147+08:00  
**结论：快速功能板测完成并通过；按键和主观画质项目结合用户现场确认。**

- 下载：SRAM临时下载成功，PDS显示PG2L100H、done bit=1，未写Flash。
- 位流SHA256：`383DAA2D21270EDA53D94D79F05F464FEB8BAE2A4710288CD600F535355C55D0`。
- 完整工程496项清单及独立/内嵌位流校验均通过。
- 采集：Hagibis，DirectShow MJPG，1920×1080。
- 运动快筛：901帧 / 30.015秒，实测采集30.018fps；UART发布30.005次/秒。
- 包内分析脚本：`PASS_QUICK_SCREEN_ONLY`；每个完整中间秒30次可检测内容变化。
- 全部采样未发现core/write fault，overflow与UART rx_errors均为0。

| 说明中的项目 | 结果 | 依据 |
|---|---|---|
| 包内哈希核验 | PASS | 外包哈希匹配；完整工程496项清单、内嵌与独立位流均通过。 |
| SRAM下载 | PASS | PG2L100H；done bit=1；383DAA2D…C55D0；未写Flash。 |
| 基线实时画面 | PASS | 1920×1080实拍图及运动录像；20秒UART基线无故障。 |
| KEY0 Brown开关 | PASS | 用户现场确认；按键录像约3.6秒关闭、9.6秒恢复几何；read_beats 150491→169016→150491。 |
| KEY2 Gamma开关 | PASS_USER_OBSERVATION | 用户确认关闭/恢复有对应变化；最终frame_state.gamma bit0=1。未用gamma_mode=0推断开关状态。 |
| KEY3 四档画质循环 | PASS_USER_OBSERVATION | 用户确认四次循环有对应变化并恢复；录像及UART无异常。档位没有直接状态读回。 |
| KEY4 OSD显隐 | PASS_USER_OBSERVATION_AND_CAPTURE | 用户确认显示/隐藏正常；第二段host_priority_and_key1录像15.70秒隐藏、20.13秒再显示。第一段录像未独立捕获清晰OSD面板。 |
| 主机质量命令优先级 | PASS_USER_OBSERVATION_AND_UART | 用户先KEY3进DN1；同源接口下发DN2+SH1并被接收；用户确认主机接管且再次KEY3能进入DN1。 |
| 主机OSD命令优先级 | PASS_USER_OBSERVATION_AND_CAPTURE | 下发标定参数OSD，第二段录像0.10秒出现，之后KEY4隐藏/再显示；主机显隐命令另有截图，最后隐藏。 |
| KEY1 BNO085姿态映射 | PASS_USER_OBSERVATION_AND_UART | BNO085有新鲜姿态，KEY1后enabled/reference/map-valid均真，参考代次0→1；转动期间画面正常且无新增故障，最终按键关闭。 |
| 主机5度仿射及恢复 | PASS | IMU映射关闭和开启时均已应用5度自动裁边并恢复0度；有截图、UART及开启状态短录像。 |
| 30秒校正帧发布率 | PASS_QUICK_SCREEN_ONLY | UART同步窗口发布率30.005/s；fault/overflow/rx_errors无增长。 |
| 30秒HDMI运动内容筛查 | PASS_QUICK_SCREEN_ONLY | 1920×1080，901帧，30fps；完整中间秒均30次变化。 |
| 恢复默认测试状态 | PASS | Brown/Gamma开启（Brown依据现场操作确认）；IMU关闭；主机画质Host(0,0)；OSD隐藏；仿射0度。 |
| 10分钟连续长稳 | NOT_TESTED | 说明中的建议后续正式验收，本次只做快速功能板测，未执行。 |

## 留存证据

- `hdmi_motion_30s_mjpg.mp4`、`hdmi_30s.json`、`hdmi_30s_per_second.csv`：有效30秒运动快筛。
- `uart_hdmi_30s_mjpg.json`、`uart_baseline_20s.json`：同步状态与基线。
- `keys_0_2_3_4.mp4/.json`：按键视频及状态；Gamma与质量档位切换依据用户现场确认。
- `host_priority_and_key1.mp4/.json`：主机优先级、KEY1参考捕获与转动。该段25秒定时检查早于用户KEY1开启，5度命令在后续有效开启状态下补齐，以`final_required_host_checks.json`为准。
- `affine_pose_enabled_5_to_0.mp4`、对应5度/0度PNG：有效姿态映射开启时的主机仿射验证。
- `bno085_before_key1.json`、`final_required_host_checks.json`、`final_status.json`：姿态数据、主机命令及最终恢复状态。
- `programming/`：实际SRAM脚本、PDS日志和下载回执。

按说明使用同源主机接口执行命令，使用OpenCV直接采集替代GUI/OBS点击操作。首次YUY2录制仅约10fps，不计入有效帧率结果；MJPG重新录制通过。

本回执仅表示说明中的快速功能筛查完成；10分钟长稳未执行，也没有把UART发布计数单独认定为不同输入画面帧率。

现场确认记录：用户两次回复“完成，画面无异常”，确认KEY0/KEY2/KEY3/KEY4均有对应变化和恢复，并最终确认KEY1已关闭、主机优先级检查正常。

录像复核补充：第二段OSD在0.10秒显示、15.70秒隐藏、20.13秒再显示；约33–36秒可见姿态/仿射几何变化，期间局部映射边缘出现黑区，片尾恢复正常矩形视图，未见整幅黑屏。本次该项验证映射与显示，不代表任意姿态无黑边。
