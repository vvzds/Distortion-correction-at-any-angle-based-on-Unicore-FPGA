# 真实素材尺度归一化补充分析

12项单侧指标转换为局部图卡平面近似cycles/mm；不据此签收画质。
镜头时间关系以用户最新确认为准：标定及采集均在更换镜头后。

| 原帧 | 位置 | cy/px | 法向px/mm | 近似cy/mm | 斜角° |
|---|---|---:|---:|---:|---:|
| before_identity_00.png | center_edge | 0.2055 | 3.9211 | 0.8058 | 0.810 |
| before_identity_00.png | outer_edge | 0.0933 | 3.5216 | 0.3287 | 2.976 |
| after_real_00.png | center_edge | 0.1801 | 3.9336 | 0.7085 | 0.730 |
| after_real_00.png | outer_edge | 0.0893 | 3.8123 | 0.3406 | 2.581 |
| before_identity_01.png | center_edge | 0.1578 | 3.9222 | 0.6188 | 0.799 |
| before_identity_01.png | outer_edge | 0.1031 | 3.5226 | 0.3633 | 2.984 |
| after_real_01.png | center_edge | 0.1980 | 3.9332 | 0.7789 | 0.718 |
| after_real_01.png | outer_edge | 0.0899 | 3.8089 | 0.3423 | 2.609 |
| before_identity_02.png | center_edge | 0.1667 | 3.9230 | 0.6540 | 0.726 |
| before_identity_02.png | outer_edge | 0.0912 | 3.5232 | 0.3214 | 2.922 |
| after_real_02.png | center_edge | 0.1902 | 3.9322 | 0.7480 | 0.760 |
| after_real_02.png | outer_edge | 0.0935 | 3.8100 | 0.3562 | 2.344 |

可比性：NOT_COMPARABLE
未满足：exposure_readback_verified, white_balance_readback_verified, slant_within_selected_method_domain, matched_radiometric_pipeline

仍需受控光照/读回曝光白平衡及合适倾角的新素材；现有4fps校正输出可用于静态采集，不代表30fps处理通过。
