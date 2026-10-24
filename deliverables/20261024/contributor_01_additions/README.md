# 一号协作者：已有材料增量归档（2026-10-24）

基于远端 `main@a500eee34965f2f343cd61ed7143a2def6bb48df` 的文件树及11份已核对Git blob哈希的归档副本进行去重。
共核对一号本地1133个原文件；688个可从仓库已有文件/归档取回，新增409份不同内容的文件；另外36个快照路径复用本次新增文件。
这里只归档已有成果，不修改生产RTL、FDC、IP、现用PC工具或正式任务表，也不晋升候选版本。

## 新增材料入口

| 分类 | 内容与当前边界 |
|---|---|
| [缓存时序方案](payload/design/AB_cache_timing_plan/01_缓存时序改进设计方案.md) | P1设计与验证计划；尚未实施，待设计方裁定 |
| [资源/告警审查](payload/verification/resource_warning_audit/reports/) | A01–A03、CW及已有原生证据；A+B seed2物理125MHz未通过 |
| [板卡UART依据](payload/docs/board_uart/UART核对结论_给设计方与执行方.md) | 厂商依据、实测准备、用户板型记录；不是最终FDC签核 |
| [映射接口探针](payload/verification/map_interface_probe/README.md) | 独立正/负例检查记录；不代表新核/整机验收 |
| [标定与G4历史验证](payload/calibration/brown4_1080p30/) | 标定核对脚本和历史日志补充；实板30fps尚不能由仿真推定 |
| [UART接收记录](payload/tools/uart_host_tool/) | T_LIM、status等历史接收及验证补充；现用根目录工具未替换 |
| [rect_wr_if历史闭环](payload/verification/) | R01、T02和修正do的既有验证记录 |

## 仓库已有，不重复上传

- [M01软件实现归档](../../20261023/review_delegation/original_archives/M01.zip)：与本地最终实现ZIP逐字节相同；P01–P09软件通过，P10实板未测。早期项目说明中的“未收到实现”不应作为这次核对后的文件存在性结论。
- [A+B R1–R4回执归档](../../20261023/G4_AB_R1_R4_review/README.md)：包含本地A+B核与G4接核候选；候选不等于生产，G4宿主仍缺匹配验收位流。
- [T02与独立进展](../AB_review_20261024/README.md)：8份本地T02文件已有同字节内容，不重复。
- 根目录 `source/rtl/rect_wr_if.v` 已存在；串口修复版代码也已包含在M01等归档。无需因本次归档覆盖现用源码。

## 取齐文件与核验

`payload/` 是缺件集合，**不是可独立运行或直接烧录的完整工程**。各历史README和历史清单保留原字节；其中引用的依赖、绝对路径、完整包文件或生成物可能不在本目录，不能直接对payload运行原完整交付校验器。

`SNAPSHOT_MANIFEST.json` 为每个原快照路径记录字节数、SHA256和唯一来源（本次payload、既有Git文件或既有ZIP成员）。新增文件内的重复内容也只存一份。还原工具只写新输出目录，不覆盖已有文件；每个Git来源、输出文件都校验哈希。

在包含本分支的仓库中运行（Python3标准库、Git；输出目录必须不存在）：

```powershell
python -B -X utf8 deliverables/20261024/contributor_01_additions/restore_snapshot.py --repo . --out C:/temp/contributor01_snapshot
```

普通完整clone可离线取齐；部分clone可能需要GitHub网络和授权下载被引用的blob。大型向量、编译数据库、软件安装包和位流未纳入快照；这些资料仍留在原本地交付目录，不能把还原通过称为完整PDS复现或上板验收。

本次已在本机核验全部1133个文件的还原字节和SHA256，并对还原后的M01执行原333项文件清单核验、UART执行U0–U5自测、缓存方案执行24项文件清单核验。详细结果见VALIDATION.json；没有重新执行RTL仿真/PDS/实板测试。
