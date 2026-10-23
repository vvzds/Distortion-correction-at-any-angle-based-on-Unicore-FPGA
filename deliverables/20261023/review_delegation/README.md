# 审验外包归档（2026-10-23）

用户要求解除本机审验瓶颈。完整分工见instructions/00_审验外包总调度.md；一号A01–A03，二号B01–B04。总说明及正式任务清单仍v2.0.4。本轮是审验委托，不是所有技术项已验收。

GitHub保存所有新增原ZIP和说明。约1.27GB的G8旧证据已在同仓库G8_followup/parts，M02和AB验收原ZIP亦已存在；不重复上传同字节的大包。recipes逐项指定这些已归档材料的完整路径、长度和SHA。克隆整个仓库后执行：

```powershell
python -B -X utf8 deliverables/20261023/review_delegation/reassemble.py --recipient all --out D:/audit_delivery_new
```

可用--recipient one或two只重组一位。输出目录中不能已有同名ZIP，程序逐源/整内包/最终ZIP核验；不依赖管理方D盘。只下载当前子目录不包含G8分片等共享依赖，请完整clone；不需要Git LFS。ZIP内所有审验材料已齐全，用户直接转交完整ZIP即可。

历史原件中的SP6.4硬限制和“G8待执行”由本轮调度说明覆盖；两版本差异不构成拒收，真实数值和证据缺陷不豁免。production G4不变。

待您转交：分别给一号、二号各一个完整合包。

本次工作主要由 GPT-6 模型完成。
