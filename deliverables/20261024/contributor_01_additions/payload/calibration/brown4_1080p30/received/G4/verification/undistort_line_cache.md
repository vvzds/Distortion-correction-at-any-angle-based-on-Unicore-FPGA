# undistort_line_cache 验证记录

验证方法：将源文件同步到任务包下ASCII路径的`sim_ascii`临时仿真区，运行ModelSim 10.7，显式 `vopt work.undistort_line_cache_tb +acc -o cache_verify_acc`，再 `vsim -c work.cache_verify_acc -do "onfinish stop; run -all; quit -f"`。`vlog/vopt`均为0 error、0 warning；2026-10-15 自校验结果为`=== ALL TESTS PASSED (err=0) === samples=72`，结果及原始 transcript 见 `logs/line_cache_*`。

观测信号：`i_load_begin/bank/row/vld/last`、`o_load_done/error`、`o_hit_a/b`及标签bank、`i_sample_req/x`、四邻域像素与`o_sample_valid`、`i_frame_clear`、预取查询 `i_prefetch_row/o_prefetch_hit`。

预期现象：120个有效返回拍逐拍写入一条源行，间隙拍不推进位置；仅正确末拍置标签有效并脉冲`o_load_done`。查询可命中四条已加载行，替换后旧标签失效；像素x=15跨256位块、x=1919复用边界；错误提前`last`报错且不置有效标签。在原7组采样之外，连续64组请求按每2拍一次提交并逐组核对四邻域，另1组验证帧首清标签后不会复用上一帧图像。合计72组，`err=0`。

工具提示：本机ModelSim退出时另打印`FileWatch(fileName)` Tcl提示；原始transcript留存。TB的PASS结果独立落盘，不把退出提示当作设计错误或测试通过条件。
