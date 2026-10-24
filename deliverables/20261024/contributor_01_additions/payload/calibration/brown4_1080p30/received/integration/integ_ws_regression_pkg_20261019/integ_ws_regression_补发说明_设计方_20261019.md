# integ_ws 回归件包补发说明（设计方，2026-10-19）

**响应**：二号《G4_整机补证复核回复》§4"第三方回归（I0–I7）"与 §6 后续建议、我方《G4_full_review_回件_接收审查结论》§5.1——补发独立重跑 I0–I7 所需的 TB / 理想链路模型 / 批仿真 runner（补证包仅附回归日志，未附运行件；我方原 I0–I7 结论为设计方单侧证据，本包使二号可独立复现）。

## 1. 包内容（12 件 + manifest）

| 文件 | 说明 |
|---|---|
| `source/rtl/`（8 件） | corr_top.v / param_mgr.v / gamma_lut.v / undistort_map.v / undistort_core.v / undistort_line_cache.v / undistort_bilinear.v / **rect_wr_if.v（V1.0 交付真件，验收通过）**——与二号 local_compile_sources_sha256.tsv G4 组 8 件**逐字节一致**（含 rect_wr_if `C201B8D2…`），二号可直接以其本机副本核对 |
| `sim_models/ideal_link.v` | 一号链路侧理想替身（DDR 数组 + 12 项协议断言），对真件同样全部生效 |
| `tb/corr_top_tb.v` | 自校验 TB，用例 I0–I7 |
| `tb/run_corr_top_full.do` | 全真件批仿真 runner（与 stub 版仅差 core 4 文件与 rect_wr_if 的编译行） |
| `tb/run_log_20261018_full_planB.log` | 我方全真件回归参考基线（末行 `=== ALL TESTS PASSED (err=0) ===`） |
| `README.md` / `status_map.json` | 环境说明 / status 32bit 位域语义 |
| `MANIFEST_SHA256.tsv` | 全件 SHA256 清单 |

## 2. 复跑方法（ModelSim 10.7，与二号本机编译环境一致）

```
# 解压到纯 ASCII 路径（二号本机中文用户名路径会使 10.7 sqlite 建库失败，你已实测）
cd <解压目录>/tb
vsim -c -do run_corr_top_full.do
```

**期望**：编译 0 错 0 警告 → I0–I7 全 PASS → 末行 `=== ALL TESTS PASSED (err=0) ===`。
关键判据：I2 逐字 golden 复制；I6 status 判据 `pub=0008_0012`（方案 B 判据——跳帧后到优先，帧 #5/6/7 逐字 golden）；I4 status 版本 0x12/params_valid/pub_count 单调。参考仿真时长：我方全真件跑约 3'23"（10.7）。

## 3. 注意事项

1. 本包 8 件 RTL 与二号本机归档一致，重跑即验证"我方补证包 corr_subsys 快照 + I0–I7 日志"的可复现性，与二号 10-19 两组编译检查（语法/绑定/端口级）形成互补——本包补功能回归级。
2. TB 断言与 ideal_link 12 项协议断言全激活，任何契约违例都会报错计数（err>0 即 FAIL）。
3. `source/rtl_v1.2_backup/`、`source/stub/` 与历史中间日志未入包（与全真件回归无关）；如需 stub 版对照，后续可补发 `run_corr_top_stub.do` + stub 2 件。
4. 相关状态更正（与我方此前表述不同，以补记为准）：**rect_wr_if.v 为 V1.0 交付真件**（10-18 验收：W0–W8 ALL PASS、I0–I7 全真件集成 ALL PASS、A01–A06 批准）——详见随包《rect_wr_if_状态更正补记_设计方_20261019.md》。该更正使二号 10-19 编译验证对象确认为全真件快照，意义增强。

## 4. 回件期望

- 复跑结果（vsim console / 退出状态）+ 本机环境（ModelSim 版本/路径）回传，我方将 I0–I7 从"设计方单侧证据"升级为"双方独立复现"；
- 如需 G5 候选版同环境对照（map 4 件替换为 G5 组），可沿用二号 compile_g5 中已有 G5 源，仅换 `undistort_map.v` 编译行即得 `run_corr_top_full_G5.do`（如需我方预置版可告知）。

设计方 2026-10-19
