# rect_wr_if 修正 do · ModelSim 10.7 实跑验证记录

> 版本：V1.0 ｜ 编制：畸变校正系统设计方 ｜ 日期：2026-10-18
> 验证对象：一号补交 `sim/run_rect_wr_if.do`（sha256=fea4ef4379b0d6ab5d7e2ed3328d41464c63b730db851fcc0902a63f7ccaafb7，T02 补交包原件）
> 前置：用户 2026-10-18 批准执行（T02 回复 §5 既定"待用户安排后执行"）
> **结论：一次通过**——编译 0 错 0 警告、W0–W8 全 PASS、判据门 err=0/tb_done=1/commits=4、进程退出码 0；E1/E2 两项勘误实跑生效；TB 输出与已交付 10-17 日志逐行逐序一致。

---

## 1. 验证环境与暂存组装

- 环境：ModelSim SE-64 10.7（D:\FPGA\MODELSIM\win64\vsim.exe，`-c` 控制台模式）
- ASCII 暂存目录：`%TEMP%\rwi_do_v2\`（10.7 的 vlog sqlite 层无法在中文路径创建 work 库——与 10-17 代跑同法、同理由，见《交付审查结论》§2.1 另注）
- 目录布局按一号 do 的锚定要求组装：`source\rtl\rect_wr_if.v` ＋ `sim\rect_wr_if_tb.v` ＋ `sim\run_rect_wr_if.do`

| 件 | 来源 | sha256 | 核对 |
|---|---|---|---|
| do | 一号 T02 补交包原件 | fea4ef43… | 与一号 SHA256SUMS 公布值一致（13/13 校验之一） |
| RTL | integ_ws\source\rtl\rect_wr_if.v（真件） | c201b8d2… | 与 10-17 暂存副本**逐字节一致**（双锁定）；integ_ws 副本与交付件一致系交付审查既定结论 |
| TB | 10-17 代跑暂存副本（当时已对交付原件 STAGED_COPY_MATCH） | 68b05608… | 10-17 代跑即用此副本产出已交付 5032B 日志 |

暂存三件组装后 STAGED_COPY_MATCH（do/tb/rtl）= **True/True/True**。

## 2. 执行方式

- 命令：`vsim -c -do sim/run_rect_wr_if.do`，工作目录 = 暂存根（root 由 do 内 `[pwd]` 回退锚定——即一号 do 头部注释给出的两种合法运行方式之一，`rect_wr_if_root` 变量路径未启用）
- 耗时 73 秒（15:36:58–15:38:11），仿真时轴 323.53ms（与 10-17 代跑一致）；`$finish` 位于 rect_wr_if_tb.v **L407**（与既知 TB 结构一致）

## 3. 结果逐项

1. **E1 修正实跑生效**：root 经 `[pwd]` 正确锚定暂存根，路径解析链（root → sim → verification/modelsim）在 transcript 中可见，无 "FAIL ModelSim: missing" 报错——10.7 `-do` 下 `info script` 返回空的缺陷不再触发。
2. **编译**：0 错 0 警告（rect_wr_if + rect_wr_if_tb，`+define+SIMULATION`）。
3. **仿真**：W0–W8 全 PASS、`=== ALL TESTS PASSED (err=0) ===`；种子三元组 **seed_up=49a2137b / seed_slot=c0213471 / seed_wr=17009bc3**（与已交付 Icarus/10.7 报告一致）。
4. **E2 修正实跑生效**：`examine -radix unsigned /rect_wr_if_tb/tb_done` → **1**（旧版 `-radix decimal` 符号扩展误读 -1 的假失败不再发生）。
5. **判据门与退出码**：err=0 / tb_done=1 / commits=4 三判据全过 → `quit -force -code 0`，**vsim 进程退出码 0**（PowerShell `$LASTEXITCODE` 直接采集，非日志推定）。

## 4. 与已交付 10-17 日志的逐项对比

对比基准与三档日志（不混淆）：

| 档 | 件 | 字节 | sha256 |
|---|---|---|---|
| 10-17 代跑原件（CRLF） | `%TEMP%\rwi_vsim\W0_W8_vsim.log` | 5032 | 321e85c1…（本次复核仍一致） |
| 转交发出/一号收件（LF，渠道行尾转换） | 工作目录 `W0_W8_vsim.log` | 4931 | 972c27ad…（= 一号 received/ 归档字节） |
| **本次 do 修正版实跑** | 工作目录 `W0_W8_vsim_do修正版实跑_20261018.log` | **5171** | **6a9dde19d0cea3b7b0831c24439536c090f967b105d4db1dbdd602fee2294586** |

对比方法：strip transcript `# ` 前缀、排除时间/路径/工具横幅行后逐行对比（与一号《核对证据.py》同法）；行尾差异（LF/CRLF）不影响分行。

结果：

- TB 相关行 76 vs 76，**唯一差异 1 行 = vlog 命令回显**：10-17 我方扁平布局 ``$root/rect_wr_if.v $root/rect_wr_if_tb.v`` vs 本次一号标准布局 ``[file join $root source rtl …] [file join $script_dir …]``——属两次 do 布局不同的命令回显差异，非 TB 行为差异；**其余 75 行（含 W0–W8 全部输出行、判据读数行）逐行且逐序完全一致**（unified diff 确认仅该行同位替换）。
- 关键统计逐项一致：W0/W1 words=960 commits=0 peak_wm=2；W2 words=1036800 commits=1；W3 定点 delay 0/4/16 全 verified、peak_wm=9；W4 BLOCK wm=1 len=3720、peak_wm=1861；W5 slot delay=512、两帧 OVERLAP、commit_backlog=1605、peak_wm=1863/peak_fifo=1862；W6 peak_wm=2；W8 四帧 commits=4、peak_wm=48；W7 协议断言全程激活。
- 新日志判据读数紧随命令行（防错位核对，与一号方法同）：err→0、tb_done→1、commits→4，三 True。
- 新日志 5171B 略大于旧 5032B：一号 do 命令序列回显略多（root/script_dir/results 变量设置、条件 vdel、头部注释行），TB 输出不受影响。

## 5. 裁定

1. 修正 do（fea4ef43…）**10.7 实跑验证通过**：E1（摆脱 `info script` 依赖）、E2（tb_done 改 `-radix unsigned`）两项勘误实跑生效；判据门 exit 0；W0–W8 行为与已交付双环境（Icarus/10.7）证据完全一致、同种子。
2. 《交付审查结论》§6 行动清单第 1 条**完全闭环**：设计方勘误（10-17）→ 一号落实修正（10-18 补交）→ 设计方实跑确认（本记录）。
3. 一号 do 可作为 rect_wr_if 后续一切 10.7 复跑的标准入口脚本（项目根 `vsim -c -do sim/run_rect_wr_if.do`）。
4. 本记录＋实跑日志本体（5171B）随下次转交一号——落实我方转交流程检查项"引用哈希必附本体"。

---

## 变更记录

| 版本 | 日期 | 内容 |
|---|---|---|
| V1.0 | 2026-10-18 | 首版：修正 do 10.7 实跑一次通过（exit 0），E1/E2 生效确认，TB 输出与已交付日志逐行逐序一致（唯一差异为 do 布局 vlog 回显行），三档日志哈希归档 |

---

*本记录由畸变校正系统设计方编制，与实跑日志本体 W0_W8_vsim_do修正版实跑_20261018.log 一并经用户转交 rect_wr_if 任务接收方（一号）。*
