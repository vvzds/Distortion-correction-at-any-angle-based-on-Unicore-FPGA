# 可选的离线人工点图测角

先按根目录README完成人工板测及回传，不必为了运行本工具推迟回传。

量化一轮时需要五张原图：本轮reference_XXX.png；停稳补偿后按S的settled_snapshot图；D后自动生成的off_after_D图；off_repeat_after_D图；D暂停时手动回到原姿态再按S的off_snapshot图。整个组内不要按R。D后姿态至少保持2秒；若需回位图，可先拍回位，再C恢复原参考。原参考保留是本版新行为。

在本目录PowerShell运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\measure_trial.ps1 -Session "D:\affine_manual\sessions\对应会话"
```

按对话框依次选择reference、corrected、off、off_repeat、returned。所有图必须为原始1920×1080 PNG，不能使用预览录像或窗口截屏。在每张图上按完全相同顺序左键点选四个固定角点/十字中心，选满按Enter。右键撤销，R重选本张，Q取消；其他图会显示带编号参考。尽量让四点覆盖大矩形并处于同一平面，用不重复的标记避免认错。

结果写入基准图所在目录下新的measurement_时间文件夹：report.md、result.json、points.json。打包回传会一并包含这些结果。点选需要人工操作，现场GUI尚未验证。软件几何回归记录为checks.json。

角度正值表示图案在图像中顺时针运动；通常与镜头滚转方向相反。它不是标定的机械角，也不能完整描述三维倾斜。默认每点误差假设为原图2px，点选不准可加-ClickError 4；敏感度不是置信区间，不因输出小数位多就认为精度高。输入角小于2°或不足敏感度五倍时不计算残余角减少比例。

off复拍和回位检查仅提示姿态/场景/选点是否重复；无法排除按D瞬间的移动。REVIEW/CONSISTENT是几何筛查，不是整机验收。程序不向串口发送任何指令，也不调用跟踪器或ECC。
