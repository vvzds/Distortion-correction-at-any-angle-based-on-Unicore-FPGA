# critical warning 专项审查资料

先读38条critical_warning专项审查报告_20261024.md和对应协作者补充单。原38台账与SCCB arc台账可直接核对；warning_audit.json保留全部2288事件，source_index.json列258资料出处/哈希，cross_checks.json列跨种子差异。

只用Python标准库复核：`python -B -X utf8 portable_recheck.py --out <新JSON文件>`。脚本只读取包内资料，输出路径必须不存在。退出0为证据检查PASS，不是告警关闭/电气/生产PASS。audit_warnings.py和supplement.py为管理方取证来源脚本（含原本机路径），移机请使用portable_recheck.py。

原38：36共享引脚待板级依据、2 UART源属性缺失；G8综合新增8条STA提示。完整合包已保留旧委托与预算资料，一位接收人只转交一个ZIP。

本次工作主要由 GPT-6 模型完成。
