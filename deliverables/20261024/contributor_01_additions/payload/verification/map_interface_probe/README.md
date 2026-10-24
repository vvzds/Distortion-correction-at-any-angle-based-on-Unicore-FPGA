# 新核心接入前接口探针与实际验证结果

2026-10-24，一号独立补充交付。为等待新优化核心期间准备接口对照工具；使用冻结A+B map作为参考，没有修改G4生产源码、AB源码、DDR接口或原FDC。

## 本轮实际结果

Icarus Verilog编译及vvp实际运行，原始版本、命令、退出码、输入/工具前后哈希和日志在`evidence/baseline_01/`。参考map SHA256为`aafbaac6f658c0f7ea6219bcb172a05f82b836ac1275651d1a0aec29251a9ee3`。

| 项目 | 实测结果 |
|---|---|
| 初始化 | 3次均为106个时钟沿间隔：初始化请求在沿n采样，init_done在沿n+106更新后为1 |
| valid延迟 | 11个时钟沿间隔：输入在沿n且沿前init_done=1时被采样，o_valid和坐标在沿n+11更新后有效 |
| 采样计数约定 | 若把起点终点都计入，分别是107/12个采样沿；后级同步always通常在下个沿才读到更新后的值。不可仅根据“C11/C12”名称接线 |
| 输入/输出核对 | 受理274个输入，输出269个恒等坐标；5个尚在流水中的输入被测试中的显式复位清空，274=269+5 |
| 连续及空拍输入 | 顺序和valid同拍核对通过，统计223组相邻输出，连续期支持II=1的本测试证据 |
| 帧参数锁存 | 初始化后改变外部畸变/仿射参数，不重新初始化，当前帧仍保持原恒等输出 |
| 边缘 | 含(0,0)、(1919,1079)和多组内部坐标；未测非法屏幕坐标 |
| 复位 | 在途5个输入被清空，无旧valid泄出；重新初始化后恢复 |
| 故障检出自查 | 隔离副本注入valid提前1沿、恒等x坐标1bit错误、输出缩为26bit，全部按预期拒绝 |

隔离故障副本在`evidence/negative_01/`中，文件名含故障名称，**仅为测试工具有效性的夹具，不是优化候选或交付替换RTL**。原map前后SHA未变；每个负例result.json的FAIL是预期检测结果，总结`summary.json`为检出自查PASS。

## 可复现入口

本包`reference/undistort_map.v`为原map只读副本，执行例如：

```powershell
python -B -X utf8 run_map_probe.py --map reference/undistort_map.v --tool-root D:/tools/iverilog/app --out evidence/local_baseline
python -B -X utf8 check_probe_detection.py --map reference/undistort_map.v --tool-root D:/tools/iverilog/app --out evidence/local_negative
```

实际工具根目录须含`bin/iverilog.exe`、`bin/vvp.exe`、`lib/ivl`。使用全新输出目录；保留失败记录。Windows入口会创建并释放私有subst映射，不打开摄像头、串口或PDS。

接收新map时保持同名冻结端口，提供完整依赖。当前入口面向单文件自包含map，若新map分文件/include/IP须先审阅并明确列入输入哈希，再扩展编译输入，不能删除缺失部分以凑通过。

本工具默认`--latency 11 --init-limit 128`。11来自本次参考实测；128是此工具的初始化看门界，不是新冻结契约。新核心若声明不同延迟/初始化上界，应提供其准确计数约定、设计依据和与A+B在途/FIFO衔接的评审；批准后作为独立候选参数运行，不能直接调参数消除失败。本工具未验证参数符号等价，仅命名端口绑定/宽度诊断与选定动态行为。

## 未覆盖、未完成

没有收到或测试新的优化核心。没有Brown4/仿射真实参数逐位等价、float64误差、全1080p帧、DDR/Column/仲裁、完整core复位、物理setup/hold或实板验证。本轮不能替代旧功能矩阵或最终新SHA的适用回归。map独立复位通过不能扩大成core-only/bridge旧回复任意交叠安全。

新核心仍需按统一材料N01–N04回传。当前A+B综合125MHz WNS−0.796/−1.226ns仍FAIL；新工具不会改变时序结论。G4板级仍暂停。
