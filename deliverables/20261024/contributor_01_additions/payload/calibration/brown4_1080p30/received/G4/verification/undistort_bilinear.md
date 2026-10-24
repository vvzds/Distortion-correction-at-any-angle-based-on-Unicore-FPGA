# undistort_bilinear 验证记录

验证方法：在 `D:/FPGA PDS/sty/collab2_undistort_core_task_pkg_v1.1/sim_ascii/sim` 使用 ModelSim 10.7 批处理 `vsim -c -do run_undistort_bilinear.do`。脚本依次运行 `vlog`、`vopt +acc`、`vsim`；TB 对独立 real 四点插值模型比对恒等权重、边界颜色、半权重和 1000 组随机数据。`vlog/vopt` 均为 0 error、0 warning，`bilinear_result.txt` 为 `=== ALL TESTS PASSED (err=0) === random_cases=1000`。

观测信号：`i_valid`、`i_p00/i_p01/i_p10/i_p11`、`i_wx/i_wy`、`o_valid/o_pixel`，以及 TB 的 `err`、`k`。

预期现象：输入有效后两拍 `o_valid=1`，`o_pixel` 与 real golden 四点插值舍入所得 RGB565 完全相等；输入无效两拍后 `o_valid=0`。最终 `err=0`、`k=1000`。

工具提示：本机 ModelSim 10.7 退出时打印 `Error: can't read "FileWatch(fileName)"`，但测试已在 `$finish` 前执行至末尾且结果文件已关闭。该 Tcl 提示不代表 RTL PASS 由控制台产生；交付时保留原始 transcript 和 TB 结果文件供复核。
