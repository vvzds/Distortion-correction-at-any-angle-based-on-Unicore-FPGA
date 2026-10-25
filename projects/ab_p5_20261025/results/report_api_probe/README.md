# 报告命令验证证据，不是P5时序结果

此目录用已有P2布线数据库验证PDS的`report_timing -input_db_file`。它只证明可以在独立目录进行报告，不重新综合或布线，且输入数据库SHA保持不变。

其中的-2.381ns等路径属于旧P2，不能作为P5结果。P5最终证据应看`results/physical_seed2`、`physical/host_seed2/report_timing`及（物理完成后才可能生成的）`results/focused_timing`。
