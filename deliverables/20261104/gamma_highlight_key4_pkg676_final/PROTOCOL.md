# UART v1 与上位机接口

## 物理层

FPGA 应用时钟125MHz；UART115200、8数据位、无校验、1停止位；B24=RX，C24=TX，3.3V。`host/control.py ports`只枚举，不打开设备；GUI点击“连接”才打开串口。串口状态没有DDR初始化位，板上初始化需通过LED、视频和帧计数联合确认。

## 数据包

所有多字节字段采用little-endian。

```
AA 55 | VERSION(1) | COMMAND(1) | LENGTH(1) | SEQUENCE(2) | PAYLOAD(LENGTH) | CRC16(2)
```

VERSION固定1；CRC16/CCITT-FALSE，多项式1021h，初值FFFFh、不反射、不作最终异或，覆盖VERSION到PAYLOAD末。标准校验串`123456789`为29B1h。最大payload64字节；包内超过约20ms无字节将重置接收状态。正常115200串口发送整包约6.34ms。

| 命令 | 请求payload | 回复 |
|---|---|---|
| 10h SET | 64字节，16个signed32 | 无独立ACK；查询active_sequence确认 |
| 20h STATUS | 0字节 | A0h、48字节、原请求sequence |
| 26h 姿态透视 | 1字节：00h关闭；01h锁定当前BNO085姿态并启用 | 无独立ACK；STATUS word 9 bit6=启用、bit7=参考有效、bit8=重算中、bit16:9=捕获代数、bit17=映射有效 |
| 30h / 32h 画质 | 1字节：0=关闭、1=柔和、2=标准、3=增强；分别设置锐化/降噪 | B0h / B2h、48字节QACK、回显请求sequence和档位 |
| 34h OSD行 | 49字节：行号0..3 + 48个ASCII字符 | 写入FPGA OSD缓存，不改变显隐状态；无逐行ACK |
| 35h OSD显隐 | 1字节：0隐藏、1显示 | 在下一帧显示边界生效 |

坏CRC、非法长度/版本及非法参数不改变active配置并增加错误计数。画质设置仅在发送端空闲时接受；被接受后返回对应QACK。TX忙、坏CRC或档位越界均不会改档，也不会回成功ACK。QACK只确认控制寄存器接受设置，不代表像素时钟域已应用或HDMI视觉效果通过。旧位流不返回B0h/B2h，主机对此报告未确认，不回退到valid_packets计数。

完整SET先进入shadow，正在处理的帧完全不变；空闲帧界将shadow原子切入active，更新active_sequence。busy期间多个完整SET仅保留最新pending。主机发送前读取状态，避免16位sequence回绕后与旧active/pending碰撞；发送后轮询确认active_sequence，而非仅把write成功当作生效。

## 16个寄存器

每项都是32位有符号整数，按表内index排列。一般用户只操作标定JSON和angle/zoom/tx/ty/shear，由`host/model.py`编码；无需手算定点值。

| index | 名称 | 格式/含义 |
|---:|---|---|
|0|n11|Q28，A00/fx|
|1|n12|Q28，A01/fx|
|2|n13|Q20，(A02-cx)/fx|
|3|n21|Q28，A10/fy|
|4|n22|Q28，A11/fy|
|5|n23|Q20，(A12-cy)/fy|
|6|fx|Q16，128…8191像素|
|7|fy|Q16，128…8191像素|
|8|cx|Q16，0…1919像素|
|9|cy|Q16，0…1079像素|
|10|k1|Q22，二阶径向的r²系数，绝对值<2|
|11|k2|Q22，r⁴系数，绝对值<2|
|12|p1|Q22，切向系数，绝对值<2|
|13|p2|Q22，切向系数，绝对值<2|
|14|mode / projective g0|旧模式：0=linear、1=adaptive Gamma。透视模式：bit0=Gamma、bit1=逐帧平滑、bit2=反馈tag有效、bit3=透视启用、bit15:4=0、bit31:16=signed Q14 g0|
|15|mode / projective g1|旧模式：bit17=逐帧目标平滑、bit16及低16位保留兼容旧标签客户端但不再产生像素标记、bit31:18固定0。透视模式：bit31:16=signed Q14 g1、bit15:0=反馈tag|

透视模式由寄存器14 bit3启用，斜率范围为signed Q14。归一化仿射坐标之后、Brown畸变之前，FPGA计算：

```
d = 1 + g0*x + g1*y
xp = x/d
yp = y/d
```

这为同一平面单应矩阵提供分母项；单应矩阵的分子仍由寄存器0…5给出。硬件只接受每个像素 `0.5 <= d <= 1.5` 的区域，其余像素填黑以避免数值发散。透视系数通过UART影子寄存器在帧界原子生效；关闭bit3时沿用旧寄存器格式和逐帧平滑语义。命令26h启用FPGA内BNO085纯旋转补偿：捕获姿态作为参考，后续姿态更新生成归一化逆映射系数并整体更新映射寄存器。报告模式切换或传感器复位会使参考失效并恢复基础映射。越过分母或系数安全范围时也会回退基础映射。该模型假定相机绕光心旋转；平移、近景视差及场景深度变化不由IMU旋转单应补偿。STATUS word 9 bit6表示已启用，bit7表示已捕获参考，bit8表示正在重算，bit16:9为捕获代数，bit17表示映射有效。

v2不再向任何视频像素写入反馈信息。旧格式bit17开启时前六个逆映射系数在每帧开始向目标推进剩余差的一半，含±1 LSB的精确收敛；bit17关闭时精确应用整组配置。Brown/内参/Gamma变化会跳过过渡，防止混合标定参数。主机必须先通过21h确认固件版本。

A是将输出屏幕坐标映射到理想无畸变平面的2×3逆仿射矩阵，屏幕原点左上、x向右、y向下。主机正角度表示显示画面顺时针旋转，以(959.5,539.5)为中心；forward顺序为shear→rotation/zoom→translation，主机求逆后编码到A。FPGA继续计算Brown多项式及像素投影，而不是上传逐像素LUT。

```
x = (A00*u + A01*v + A02 - cx)/fx
y = (A10*u + A11*v + A12 - cy)/fy
r2 = x*x+y*y
radial = 1+k1*r2+k2*r2*r2
sx = fx*(x*radial+2*p1*x*y+p2*(r2+2*x*x))+cx
sy = fy*(y*radial+p1*(r2+2*y*y)+2*p2*x*y)+cy
```

|x|或|y|>1.5会在多项式前屏蔽，防止极端指令溢出；越出源图范围的输出填黑。主机preflight检查每个tile的源AABB，不接受超过256×256 patch的变换；硬件仍保留overflow_tiles计数，越界tile填黑。zoom支持0.5…8，但并非此范围内所有与任意shear/translation的组合都保证有效视场或30fps。应对实际指令运行preflight，并以板端计数确认实际性能。

## STATUS的12个uint32

| word | 字段 |
|---:|---|
|0|magic=554E4401h|
|1|低16位active_sequence，高16位最近pending_sequence（pending flag决定是否仍待切换）|
|2|累计完整校正帧发布数，32位回绕|
|3|上一完整帧处理cycles，包括取得源/目标slot至发布的等待|
|4|上一帧读请求等待及返回空拍数|
|5|上一帧输出写回等待数|
|6|上一帧源图读取256位beats数|
|7|上一帧映射无效像素数|
|8|累计patch overflow tiles|
|9|flags|
|10|UART错误数|
|11|有效包计数，状态快照可能不包含本次STATUS本身|

flags：bit0 busy、bit1 pending、bit2 core_fault、bit3 write_fault、bits5:4 Gamma mode（0=linear、1=.6、2=1.6、3=高光压缩）、bit6姿态映射启用、bit7参考有效、bit8姿态系数重算中、bits16:9参考捕获代数、bit17姿态映射有效。主机`processing_capacity_fps=125000000/cycles`仅是上一帧处理能力；`monitor`中的`actual_new_frame_fps=发布帧数差/主机单调时钟间隔`才用于板上实际更新帧率。两者均不等同于显示器报告的刷新率。

## Gamma策略

统计使用插值后、增强前且映射有效的RGB565像素，近似亮度为`2*(R5+G6+B5)`；输出黑边不参与统计。上一帧均值<70进入gamma=.6，已在该模式且均值<90时保持；均值>190进入gamma=1.6，已在该模式且均值>170时保持。未命中整体暗/亮模式时，亮度不低于220的像素占比超过1/16进入模式3；已在模式3时，以1/32作为退出迟滞阈值，否则回到linear。模式在帧界锁存，所以检测有一帧统计反馈延迟。

模式3使用逐通道RGB565查表：低于通道满量程的75%不变；其上以`knee + span * z^1.6`压缩非饱和高光，满量程值保持白点。它能压低接近白点但尚未剪切的高光，不会恢复传感器已剪切丢失的纹理，也不替代相机曝光/增益控制。离线预览按单张静态图的收敛统计选择模式，不模拟视频的一帧迟滞。


## v2无画面标记反馈：21h

请求0字节，响应A1h、48字节，原请求sequence与标准CRC。12个uint32依次为：magic=534D5432h、最近发布帧数、实际发布帧的n11/n12/n13/n21/n22/n23（六个signed32，与SET定点格式相同）、再次发布帧数、该帧Gamma enable、该帧寄存器15、能力/版本=00020001h。快照在一个时钟内原子取得，系数是实际渲染值而非最新目标值。此状态表示DDR已发布，不代表HDMI已扫描或采集卡已解码；主机需估计并调节采集链时间关联。
