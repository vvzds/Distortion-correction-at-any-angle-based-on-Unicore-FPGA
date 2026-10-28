# uart_host_tool T_LIM 修复通知（设计方）

> 版本：V1.0 ｜ 编制：畸变校正系统设计方 ｜ 日期：2026-10-18
> 致：uart_host_tool 任务接收方
> 事由：接收方自主决策 U-D02 独立发现的 **T_LIM** 缺陷（与 undistort_core 任务 V12-01 同源）已在设计方侧完成修复并全量回归通过（2026-10-17）。本通知同步修复内容、参考件新基线哈希与接收方对应改动项。

---

## 1. 缺陷与修复内容

| 项 | 内容 |
|---|---|
| 缺陷位置 | 参考件 param_mgr.v 第 305 行，平移参数（tx/ty）合法界限常量 |
| 原实现（废止） | `32'sh0100_0000`——16.16 定点下等于 **±256.0**，系笔误 |
| 协议规格界限 | **±4096.0**（定点编码 ±0x1000_0000，即数值 ×0x10000） |
| 修复 | 常量改为 `32'sh1000_0000`；±4096.0 端点含入判合法（valid1）、越界 1LSB 判非法（valid0），与 V1.2 协议文档平移界限条款一致 |
| 修复前影响 | tx/ty 绝对值落在 (256.0, 4096.0]（含负向对称区间）的**合法**参数组被 `o_params_valid` 误判为 0，核心拒启 |

## 2. 修复验证（设计方本机 ModelSim 10.7，2026-10-17）

1. 参考 TB 新增 **S13c–S13h 六向量**（0x02 帧恒等仿射）：tx=±4096.0、ty=+4096.0 端点含入均 valid1；tx=0x1000_0001（+4096.0+1LSB）、ty=0xEFFF_FFFF（−4096.0−1LSB）越界 1LSB 均 valid0；S13h 恢复帧保证 S14 整体 valid1。
2. 设计行为说明：非法参数组同样执行影子组 swap 并发出 `o_param_updated` 脉冲（`o_params_valid=0` 时核心不启动）——TB 脉冲总数期望由 10 增至 16。
3. 三段回归全绿：param_mgr ALL PASSED（err=0，pulses=16）；gamma_lut G0–G6（err=0）；corr_top I0–I7（err=0，I6 status=0x0007_0012 冻结判据一致）。
4. 回归日志固化于设计方 `integ_ws\tb\run_log_20261017_tlimfix{,_param_mgr,_gamma}.log`，可按需索取。

## 3. 参考件新基线（供接收方机器核对/更新本地 01_ref 副本）

| 文件 | 修复后 SHA256 |
|---|---|
| param_mgr.v | `3B759A9712B1560BC33CC2801D29E24874E691041E20DC8F700F25366F04617A` |
| param_mgr_tb.v | `04BEC0071562DF4FD1F895FAA7FC1D5DF6460BA0006F24DFE50B96048478C25D` |

- 修复后 param_mgr.v 三副本（integ_ws\source\rtl、collab2_undistort_core_task_pkg\01_ref、**uart_host_tool_task_pkg\01_ref**）哈希逐一验证一致；param_mgr_tb.v 两包 01_ref 一致。
- 二号 undistort_core V1.2 交付包内 `verification\reference_package\01_ref` 保持交付时原样未动（属该包验收历史状态，与本修复无关）。

## 4. 接收方行动项（一行级，不阻塞既有交付验收结论）

1. **删除/调整 `warn_reference_limits` 中的 ±256 警告分支**：该警告因 T_LIM 错误常量（±256.0）而设，修复后 ±4096.0 内的 tx/ty 全部合法，保留将误导用户；工具协议层 **±4096 预检维持不变**（该界限正确，无需改动）。
2. 如接收方保留本地 01_ref 参考副本，按 §3 哈希更新。
3. 可选回归建议（板级或全真件联调时）：下发一条 tx=+1000.0 的 0x02 帧（落在原误判区间 (256, 4096] 内）——修复前 RTL 拒收（params_valid=0）、修复后 valid1；经 0x05 回读 status 的 bit8（params_valid）核验，可配合已转交的《status位域冻结确认书_20261015》与 status_map.json 位域解码。

## 5. 不受影响项

0x02 帧 25 字节协议、0x03 分帧、TX_GAP、status 位域语义、工具其余全部功能**零改动**；本次修复仅涉参考件 param_mgr.v 单常量与参考 TB 向量增补，工具协议实现无需任何返工。

---

*本通知由畸变校正系统设计方编制，经用户转交 uart_host_tool 任务接收方后生效。修复详情另见《undistort_core_V1.2_验收回复_设计方_20261017.md》V12-01 闭合章节。*
