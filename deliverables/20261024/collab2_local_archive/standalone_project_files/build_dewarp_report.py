from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pathlib import Path

OUT=Path(r'C:\Users\叶翔\Documents\Codex\2026-09-17\wo\outputs'); OUT.mkdir(exist_ok=True)
FN=OUT/'2026_FPGA_紫光同创赛道二_畸变图像校正详细实施报告.docx'
d=Document(); sec=d.sections[0]
for s in d.sections: s.top_margin=Inches(.68); s.bottom_margin=Inches(.65); s.left_margin=Inches(.72); s.right_margin=Inches(.72)
for n,sz in [('Normal',9.6),('Title',20),('Heading 1',14.5),('Heading 2',11.5)]:
 st=d.styles[n]; st.font.name='Microsoft YaHei'; st._element.rPr.rFonts.set(qn('w:eastAsia'),'Microsoft YaHei'); st.font.size=Pt(sz); st.font.color.rgb=RGBColor(0,0,0)
 if n!='Normal': st.font.bold=True
d.styles['Normal'].paragraph_format.line_spacing=1.15; d.styles['Normal'].paragraph_format.space_after=Pt(4)
def shade(c,color):
 p=c._tc.get_or_add_tcPr(); x=OxmlElement('w:shd'); x.set(qn('w:fill'),color); p.append(x)
def margin(c):
 p=c._tc.get_or_add_tcPr(); x=OxmlElement('w:tcMar'); p.append(x)
 for k in ['top','start','bottom','end']:
  e=OxmlElement('w:'+k);e.set(qn('w:w'),'90' if k in ['top','bottom'] else '110');e.set(qn('w:type'),'dxa');x.append(e)
def borders(t):
 p=t._tbl.tblPr; x=OxmlElement('w:tblBorders')
 for k in ['top','left','bottom','right','insideH','insideV']:
  e=OxmlElement('w:'+k);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'6');e.set(qn('w:color'),'D9D9D9');x.append(e)
 p.append(x)
def table(h,rows,widths=None):
 t=d.add_table(rows=1,cols=len(h));t.style='Table Grid';t.alignment=WD_TABLE_ALIGNMENT.CENTER;borders(t)
 for i,x in enumerate(h):
  c=t.rows[0].cells[i];c.text=x;shade(c,'17365D');margin(c);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER;c.paragraphs[0].alignment=WD_ALIGN_PARAGRAPH.CENTER
  for r in c.paragraphs[0].runs:r.font.color.rgb=RGBColor(255,255,255);r.font.bold=True;r.font.size=Pt(8.8)
 for j,row in enumerate(rows):
  cs=t.add_row().cells
  for i,x in enumerate(row):
   c=cs[i];c.text=x;margin(c);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
   if j%2:shade(c,'F3F7FB')
   for p in c.paragraphs:
    p.paragraph_format.space_after=Pt(0);p.paragraph_format.line_spacing=1.05
    for r in p.runs:r.font.size=Pt(8.5)
   if i==0:c.paragraphs[0].alignment=WD_ALIGN_PARAGRAPH.CENTER
 if widths:
  for row in t.rows:
   for c,w in zip(row.cells,widths):c.width=Inches(w)
 d.add_paragraph().paragraph_format.space_after=Pt(1)
def p(x='',style=None):return d.add_paragraph(x,style)
def h(x,l=1):return d.add_heading(x,l)
def code(x):
 q=d.add_paragraph();q.paragraph_format.left_indent=Inches(.15);q.paragraph_format.right_indent=Inches(.12);q.paragraph_format.space_after=Pt(5)
 r=q.add_run(x);r.font.name='Consolas';r._element.rPr.rFonts.set(qn('w:eastAsia'),'Consolas');r.font.size=Pt(7.4);return q
def bullet(x):d.add_paragraph(x,style='List Bullet')

t=d.add_paragraph(style='Title');t.alignment=WD_ALIGN_PARAGRAPH.CENTER;t.add_run('2026 FPGA 紫光同创赛道二\n任意角度畸变矫正详细实施报告')
s=d.add_paragraph('面向实时视频去畸变的可落地 FPGA 方案  |  基础任务与高阶任务  |  公式 代码 知识来源');s.alignment=WD_ALIGN_PARAGRAPH.CENTER;s.runs[0].italic=True;s.runs[0].font.size=Pt(10)
h('一 先给结论',1)
p('最稳妥的参赛实现不是在 FPGA 内实时求复杂相机方程，而是“PC 离线标定并生成映射表，FPGA 在线查表和插值”。离线阶段用棋盘格得到镜头参数；在线阶段对输出图的每个像素反向找到输入图坐标，再用双线性插值取四个邻点合成像素。这样公式只在 PC 端运行一次，FPGA 只做地址、缓存和乘加，易于达到实时性。')
p('本报告严格按官方选题指南的三项基础任务和三项高阶任务组织。双路并线拼接作为可选展示扩展，不替代赛题列出的高阶任务；它用于更直观地展示矫正后图像可支持后续拼接。')
h('二 项目目标与验收口径',1)
table(['目标','基础版本必须达到','高阶版本拉开差距'],[
['输入输出','HDMI 或摄像头输入；HDMI/LCD 输出校正结果；一路稳定显示。','支持多分辨率、双路输入、动态切换校正参数。'],
['校正对象','桶形或枕形镜头畸变；棋盘格直线在校正后明显变直。','鱼眼大视场、边缘区域精度优化、畸变与透视联动。'],
['实时性','先固定 720p 或题目要求分辨率，逐帧无撕裂、无错行。','720p60 或 1080p60；报告端到端延迟、带宽、资源、功耗。'],
['结果证据','校正前后同一棋盘格、网格纸或直线场景对比。','重投影误差、直线偏差、PSNR/SSIM、连续运行和异常恢复记录。'],
], [1.05,2.65,2.6])
h('三 赛题原话与任务分解 对照官方选题指南第10页',1)
p('以下引文来自用户提供的《全国大学生嵌入式芯片与系统设计竞赛 2026 FPGA 创新设计赛道选题指南 紫光同创》，选题二“基于紫光同创 FPGA 的任意角度的畸变矫正”。引文后的内容是本报告的工程分解，不是赛题原文。')
table(['任务层级','赛题原话','拆成可执行小任务','完成判据'],[
['基础任务 1','“图像采集与显示链路：实现视频流（如 HDMI 或摄像头接口）的采集、缓存与显示，构建完整的图像数据通路。”','摄像头 SCCB 初始化 -> DVP/HDMI 接收 -> CDC FIFO -> DDR3 ping-pong 帧缓存 -> HDMI 发送 -> ILA 抓帧号。','原图能稳定输入并显示；连续 30 分钟无错行、撕裂、黑屏。'],
['基础任务 2','“畸变模型实现：在 FPGA 中实现基于二阶径向畸变（及切向畸变）的坐标映射算法，将带有畸变的原始像素坐标转换为无畸变的理想坐标。”','真实棋盘格标定 -> 读取 K、k1、k2、p1、p2 -> Q 格式量化 -> 输出像素反向映射 -> 坐标越界掩码。','用真实标定参数；网格/黑方块校正后直线度明显改善。'],
['基础任务 3','“图像重采样：实现基础的图像插值算法（如双线性插值），根据映射后的坐标提取像素值，消除矫正后图像中的黑边或空洞现象。”','读取映射坐标 -> 取 2x2 邻点 -> Q0.8 双线性插值 -> 边界填充/有效区裁剪 -> RGB 三通道并行。','输出连续，无坐标空洞；与 PC OpenCV 参考图逐像素对比。'],
['高阶任务 1','“任意角度与动态矫正：结合外部传感器（如 IMU）或上位机指令，实现相机在发生倾斜或旋转等任意角度变化时的动态畸变矫正与仿射变换。”','BMI270/MPU6050 读取姿态或 PC 串口下发角度 -> 计算/查表 sin cos -> 双缓冲更新仿射矩阵 -> 帧边界原子切换参数。','转动相机或修改角度后，画面旋转/倾斜校正稳定且无半帧撕裂。'],
['高阶任务 2','“硬件加速与流水线优化：针对复杂的坐标映射和浮点/定点运算，实现图像的实时矫正。”','浮点改 Q 格式 -> 乘加分级寄存器 -> DDR 突发读与请求合并 -> map 缓存 -> PDS 时序收敛。','报告 1080P@30/60 或实际目标帧率、端到端延迟、Fmax、资源占用。'],
['高阶任务 3','“自适应预处理：针对强光、夜间等复杂光照环境，在矫正前或矫正过程中集成自适应 Gamma校正或直方图均衡等图像增强算法，提升极端条件下的矫正效果。”','亮度直方图/CDF 或 Gamma LUT -> 帧间统计 -> 参数限幅 -> 预处理后再去畸变 -> 强光/夜间回归测试。','复杂光照下网格边线和细节可见；不放大噪声、不影响实时帧率。'],
], [.65,2.35,2.65,1.3])
h('四 系统总架构与数据流',1)
p('视频采集 HDMI RX/摄像头 -> 输入帧缓冲 DDR3 -> 映射表 ROM/DDR -> 坐标与边界判断 -> 四邻像素读取 -> 双线性插值 -> 输出 FIFO -> HDMI TX/LCD。配置通道 UART/按键/以太网 -> 寄存器 -> 选择映射表。')
table(['模块','实现内容','为什么需要它'],[
['采集与时序','解析 RGB、de、hs、vs，写入 DDR；记录帧开始。','去畸变是随机读源坐标，不能简单边进边出，通常需要帧缓存。'],
['离线标定','棋盘格多姿态照片 -> 相机内参与畸变系数 -> map_x/map_y。','同一镜头的参数可重复使用，把复杂浮点计算移出 FPGA。'],
['映射地址','输出像素 (u,v) 查 map 得源坐标 (x,y)。','采用反向映射，保证每一个输出像素都能被填满。'],
['插值重建','读取 P00、P01、P10、P11，按小数坐标加权。','避免最近邻采样带来的明显锯齿。'],
['显示与调试','原图/校正图切换，叠加坐标、FPS、map 越界计数。','答辩时能证明校正发生在 FPGA，而非电脑后处理。'],
], [1.1,2.2,3.0])
h('四 基础任务 如何完成',1)
table(['编号','基础任务','实施步骤','验收'],[
['B1','图像采集与显示链路 赛题原话','直接运行紫光同创板卡 HDMI RX/TX 例程；先实现原样回环，再插入 OSD。','输入稳定锁定，连续运行 30 分钟无花屏。'],
['B2','采集标定数据','打印棋盘格，固定镜头焦距/分辨率；在中心、四角、近远距离采集 15 至 25 张。','每张都能检测到全部内角点；图像覆盖画面四角。'],
['B3','生成映射表','PC 用 OpenCV 标定，生成“每个输出像素对应的输入坐标” map_x、map_y；导出定点二进制。','PC 的 remap 结果与 FPGA 使用同一 map 的结果视觉一致。'],
['B4','FPGA 反向查表','以输出 raster 的 u/v 为地址读 map；整数部分是 DDR 像素地址，小数部分是插值权重。','校正后棋盘格直线明显变直，边缘不出现大面积空洞。'],
['B5','双线性插值','从帧缓存读 2x2 四点，按公式合成 RGB 三通道。','文字/斜线无明显最近邻马赛克；越界填黑或背景色。'],
['B6','完整证据','保存 RTL、约束、标定脚本、map 文件、仿真、实测图片与资源报告。','其他成员可按 README 重建工程并复现。'],
], [.45,1.1,3.15,1.55])
h('四一 基础任务一 图像采集与显示链路 赛题原话与逐步实现',1)
p('赛题原话：基础任务一“图像采集与显示链路”。这项任务的边界不是“屏幕亮了”即可，而是从摄像头或 HDMI 输入开始，经过 FPGA 时钟域、像素格式、缓存，最终以正确行场时序输出到 HDMI 显示器；这是后续畸变校正模块的输入和输出底座。')
table(['步骤','要完成的 RTL 或操作','输入与输出','验收证据'],[
['1 硬件连线','OV5640 的 D[7:0]、PCLK、VSYNC、HREF、XCLK、SCCB_SCL/SDA 接到板卡匹配转接板；HDMI OUT 接显示器。','相机并行 DVP -> FPGA IO。','拍照留存接线与丝印；核对引脚约束 .sdc/.cst。'],
['2 时钟','PLL 生成相机 XCLK（按模组配置）及 HDMI 像素时钟；每个时钟域独立复位。','系统时钟 -> xclk、pix_clk、ddr_clk。','示波器/ILA 看到稳定时钟；复位后锁定信号为 1。'],
['3 相机初始化','SCCB/I2C 状态机逐项写 OV5640 寄存器：软复位、时钟、输出 RGB565、分辨率、帧率、镜像。','寄存器表 -> SCCB 写时序。','读回关键寄存器或用 ILA 抓 ACK；无 ACK 先排查电平与地址。'],
['4 DVP 采集','在 PCLK 上升沿、HREF 有效时采样 D[7:0]；每两个字节拼一像素 RGB565；VSYNC 清零行列计数。','DVP 8bit -> rgb565、pixel_valid、x、y。','ILA 查看 x 从 0 递增至 W-1，y 从 0 递增至 H-1。'],
['5 跨域与帧缓存','采集侧写异步 FIFO/DDR，显示侧读 DDR；帧首交换 ping/pong 缓冲区。','cam_clk -> DDR -> hdmi_clk。','输入/输出帧号连续；不花屏、不半帧、不跨帧。'],
['6 HDMI 显示','产生 hsync、vsync、de 与 RGB；未激活区输出黑色，激活区读取当前帧像素。','rgb565/888 -> HDMI TX。','显示器识别分辨率；持续运行 30 分钟无黑屏。'],
], [.5,2.65,1.6,1.4])
p('最小 DVP 像素拼接逻辑如下。它只展示采集核心；真实工程还需加入跨时钟 FIFO 与丢帧保护。')
code("""always @(posedge cam_pclk) begin\n  if (cam_vsync) begin x <= 0; y <= 0; byte_sel <= 0; end\n  else if (cam_href) begin\n    if (!byte_sel) begin hi_byte <= cam_d; byte_sel <= 1'b1; end\n    else begin\n      rgb565 <= {hi_byte, cam_d}; pixel_vld <= 1'b1; byte_sel <= 1'b0;\n      if (x == IMG_W-1) begin x <= 0; y <= y + 1'b1; end else x <= x + 1'b1;\n    end\n  end else begin pixel_vld <= 1'b0; byte_sel <= 1'b0; end\nend""")
p('解释：OV5640 的 RGB565 每个像素占两个 8bit 时钟周期；hi_byte 暂存第一个字节，第二个字节到来后拼成 16bit 像素。HREF 表示当前行有效，VSYNC 标志帧边界。RGB565 中红 5 位、绿 6 位、蓝 5 位；后续双线性插值可分别扩展到 8bit 后处理。')
p('知识来源：OV5640 模组数据手册/所购转接板原理图决定具体寄存器和时序；盘古板卡的 HDMI/DDR 例程与用户手册决定引脚和 IP 配置。视频采集采用 DVP 并行采样和异步 FIFO/DDR 帧缓存，这是把相机像素时钟与显示时钟可靠隔离的常用硬件方法。')
h('四二 基础任务二 畸变模型实现 原话与分解',1)
p('赛题原话：“畸变模型实现：在 FPGA 中实现基于二阶径向畸变（及切向畸变）的坐标映射算法，将带有畸变的原始像素坐标转换为无畸变的理想坐标。”推荐采用“输出像素反向寻址输入像素”。不要做输入像素正向推送到输出图，因为正向映射容易留下未写到的空洞。')
table(['小任务','具体实现','关键检查'],[
['真实标定','固定分辨率和镜头，采集 15 至 25 张棋盘格；OpenCV 得到 K、dist；保存 .npz 与标定照片。','赛题明确要求参数基于真实相机标定，不能编造。'],
['坐标归一化','对输出像素 u,v 计算 x=(u-cx)/fx、y=(v-cy)/fy。','fx、fy、cx、cy 与画面分辨率必须同一套；改分辨率就重新生成 map。'],
['二阶径向模型','r2=x*x+y*y；scale=1+k1*r2+k2*r2*r2；xd=x*scale，yd=y*scale。','先只实现 k1,k2；这是赛题要求的二阶径向项。'],
['可选切向模型','xd += 2*p1*x*y+p2*(r2+2*x*x)；yd += p1*(r2+2*y*y)+2*p2*x*y。','基础成功后再打开 p1/p2；用参数开关便于定位问题。'],
['反向地址','sx=fx*xd+cx，sy=fy*yd+cy；sx/sy 的整数部分为像素地址、小数部分为插值权重。','sx<0、sx>W-2、sy<0、sy>H-2 时标记 invalid，避免读越界。'],
], [1.0,3.65,2.3])
h('四三 基础任务三 图像重采样 原话与分解',1)
p('赛题原话：“图像重采样：实现基础的图像插值算法（如双线性插值），根据映射后的坐标提取像素值，消除矫正后图像中的黑边或空洞现象。”这里的关键是先得到 sx/sy，再取其周围四个源像素。黑边不能靠“错误复制”掩盖：基础版采用有效 ROI 裁剪或边界复制，高阶版可做平滑过渡。')
table(['小任务','具体实现','验收'],[
['四点取样','x0=floor(sx)，y0=floor(sy)，读 P00(x0,y0)、P01(x0+1,y0)、P10(x0,y0+1)、P11(x0+1,y0+1)。','对一个固定 sx=10.5、sy=20.25 的测试点，ILA 中四点地址正确。'],
['定点权重','dx=sx 小数部分，dy=sy 小数部分，均以 Q0.8 保存。','dx/dy 变化平滑；权重和恒为 1。'],
['双线性合成','使用报告第八节公式；RGB 三通道各用一个并行插值器或时分复用。','棋盘斜线平滑，无最近邻块状感。'],
['空洞/黑边','invalid 区输出背景色或采样最近有效边界；优先使用标定时计算的有效 ROI。','画面没有随机黑点；黑边为规则裁剪区且在文档中说明。'],
], [1.0,3.65,2.3])
h('五 高阶任务 建议按这个顺序做',1)
table(['优先级','高阶任务','完成方式','量化证据'],[
['H1','高分辨率实时化','DDR 突发读、行请求合并、读请求 FIFO、双缓冲；坐标与插值流水化。','720p60/1080p60 下 FPS、时延、DDR 带宽、无丢帧。'],
['H2','高精度模型','基础版仅 k1,k2；高阶加入 k3,p1,p2 或 fish-eye 标定，比较不同模型误差。','校正后棋盘格重投影误差和边缘直线残差。'],
['H3','资源优化','map 从逐像素表改为稀疏网格表；网格内再做线性插值；坐标使用 Q 格式。','BRAM/DDR 容量和 LUT/DSP 使用率前后对比。'],
['H4','在线可配置','保存多套镜头 map；UART/按键切换分辨率、镜头号、裁剪和缩放。','现场 10 秒内切换并输出正确画面。'],
['H5','双路校正与并线拼接','每路先独立去畸变，再用标定的单应矩阵/固定偏移映射到公共画布，重叠区羽化。','展示单路、双路、重叠区，并报告接缝亮度差。'],
['H6','品质/稳定性','插值前色彩校正、无效区掩码、帧序号监控、输入断链自动恢复。','PSNR/SSIM、温升、功耗、断插恢复时间。'],
], [.55,1.28,3.15,1.27])
h('五一 高阶任务一 任意角度动态矫正 最简公式',2)
p('赛题要求的仿射变换可先只实现二维旋转。以画面中心 cx、cy 为旋转中心，给定角度 theta：')
code("""xr = u - cx;  yr = v - cy\nsx = cos(theta)*xr - sin(theta)*yr + cx\nsy = sin(theta)*xr + cos(theta)*yr + cy""")
p('解释：先将像素移到中心坐标，再用 sin/cos 把它旋转，最后移回画面。FPGA 不做实时浮点三角函数：PC 离线或上位机把 sin(theta)、cos(theta) 量化为 Q1.15 数；角度改变时在帧 VSYNC 到来才交换新矩阵，避免半帧使用新参数、半帧使用旧参数。IMU 只负责提供 theta，畸变公式仍可复用基础版本。')
h('五二 高阶任务三 自适应预处理 最简 Gamma 公式',2)
code('Yout = 255 * (Yin / 255) ^ gamma')
p('解释：Yin/Yout 是 0 到 255 的亮度。gamma 小于 1 会提亮暗部，gamma 大于 1 会压暗过曝区域。硬件不求幂：将 256 个 Yin 对应的 Yout 在 PC 预先算好，放进 256x8 的 Gamma LUT；每个像素只查表，最快也最容易验证。Gamma 只处理亮度 Y，颜色可保持 Cb/Cr 不变，减少偏色。')
h('六 知识点一 数据采集和相机标定',1)
p('方法：张正友棋盘格标定的工程实现可直接使用 OpenCV 的 findChessboardCorners 与 calibrateCamera。实际操作中，棋盘格必须覆盖中央和四角；焦距、分辨率、镜头位置一旦变化，就要重新标定。OpenCV 官方教程建议至少使用约 10 张棋盘格图，更多姿态通常更稳。')
table(['符号','最简单含义','如何得到'],[
['fx fy','像素单位的横向/纵向焦距','OpenCV 标定输出 cameraMatrix。'],
['cx cy','光轴中心在图像上的像素坐标','OpenCV 标定输出 cameraMatrix。'],
['k1 k2','主要径向畸变系数','OpenCV 标定输出 distCoeffs；基础版可只保留两项。'],
['p1 p2','切向畸变系数','镜头装配倾斜引入；基础版可先置零。'],
], [1.0,2.6,2.65])
p('来源：OpenCV 官方 Camera Calibration 文档。该文档说明镜头畸变主要分为径向畸变和切向畸变，并给出内参与畸变系数模型。链接：https://docs.opencv.org/5.0/main_modules/calib.html')
h('七 知识点二 最简畸变公式及解释',1)
p('基础版只使用径向畸变，公式最少，足以处理多数桶形/枕形问题。先把像素坐标归一化：')
code('x = (u - cx) / fx        y = (v - cy) / fy        r2 = x*x + y*y')
p('u、v 是一个理想校正图上的像素位置；x、y 是以光心为原点、以焦距归一化后的坐标；r2 是该点离中心的“距离平方”。离中心越远，r2 越大，所以畸变影响会自动在边缘变强。')
code('scale = 1 + k1*r2 + k2*r2*r2\nxd = x * scale             yd = y * scale\nsx = fx*xd + cx             sy = fy*yd + cy')
p('scale 是半径缩放比例。k1、k2 由标定给出；桶形/枕形的正负关系会随模型方向而变，不要手填猜测，应直接使用标定工具生成 map。sx、sy 表示“输出像素 (u,v) 应去原畸变输入图的哪个位置取值”。这就是反向映射：输出端主动找输入端，因而不会在输出图上留下空洞。')
p('如果基础模型边缘仍不直，再增加切向畸变：')
code('xd = x*scale + 2*p1*x*y + p2*(r2 + 2*x*x)\nyd = y*scale + p1*(r2 + 2*y*y) + 2*p2*x*y')
p('p1、p2 描述镜头与传感器不完全平行造成的非对称偏移。基础任务可以把 p1=p2=0；高阶任务再启用。完整公式来源：OpenCV 官方相机标定文档。')
h('八 知识点三 双线性插值公式及解释',1)
p('map 查到的 sx、sy 往往不是整数。令 x0=floor(sx)，y0=floor(sy)，dx=sx-x0，dy=sy-y0；P00、P01、P10、P11 分别是左上、右上、左下、右下四个像素。对 R/G/B 每个通道分别计算：')
code('Pout = P00*(1-dx)*(1-dy) + P01*dx*(1-dy)\n     + P10*(1-dx)*dy     + P11*dx*dy')
p('解释：dx 是横向靠近右像素的程度，dy 是纵向靠近下像素的程度。四个权重相加永远等于 1，因此亮度不会被无故放大或缩小。硬件中不使用浮点：把 dx、dy 存成 Q0.8（0 到 255），乘法后右移 16 位即可。')
code('wx = sx_frac[7:0]; wy = sy_frac[7:0];\n// 一个颜色通道，四点均为 8 bit\nacc = p00*(256-wx)*(256-wy) + p01*wx*(256-wy)\n    + p10*(256-wx)*wy       + p11*wx*wy;\npout = (acc + 16\'d32768) >> 16;  // 加 0.5 LSB 后四舍五入')
h('九 离线生成映射表的 Python 参考代码',1)
p('此脚本是数据采集和公式落地的关键：它读取棋盘格标定结果，生成 FPGA 使用的 Q12.8 坐标表。map 每个输出像素写两个 32 位数：sx 和 sy。720p 逐像素表约 7.0 MiB，因此应放 DDR/Flash；BRAM 只缓存当前读出的坐标和像素。')
code("""import cv2, numpy as np\n# 用多张棋盘格照片得到 K, dist；这里假定已经保存为 calibration.npz\nz = np.load('calibration.npz'); K, dist = z['K'], z['dist']\nW, H = 1280, 720\nnewK, roi = cv2.getOptimalNewCameraMatrix(K, dist, (W,H), 1, (W,H))\nmapx, mapy = cv2.initUndistortRectifyMap(K, dist, None, newK, (W,H), cv2.CV_32FC1)\n# Q12.8：低 8 位为插值小数，高位为像素整数\nmx = np.clip(np.rint(mapx * 256), 0, (W-1)*256).astype('<u4')\nmy = np.clip(np.rint(mapy * 256), 0, (H-1)*256).astype('<u4')\nwith open('map_xy_q8.bin','wb') as f:\n    for y in range(H):\n        for x in range(W):\n            f.write(mx[y,x].tobytes()); f.write(my[y,x].tobytes())\nprint('map generated, roi=', roi)""")
p('标定照片的采集代码可采用 OpenCV 官方流程：findChessboardCorners 找内角点，cornerSubPix 做亚像素优化，再用 calibrateCamera 求 K 与 dist。不要用一张棋盘格；不同角度、不同位置的多张照片才能约束镜头边缘。')
h('十 FPGA 核心 RTL 骨架',1)
p('以下代码刻意把“DDR 四点读出”封装成外部接口，因为不同紫光同创板卡的 DDR IP/AXI 接口不同；这段模块完成最容易出错的定点双线性运算。实际工程将坐标查询、DDR 读控制、插值器做成 3 个模块并用 valid/ready 流水连接。')
code("""module bilinear_q8(\n input wire clk, input wire rst_n, input wire in_vld,\n input wire [7:0] p00,p01,p10,p11,  // 单色或 RGB 的一个通道\n input wire [7:0] dx,dy,\n output reg out_vld, output reg [7:0] pout);\n reg [8:0] ix, iy; reg [33:0] sum;\n always @(posedge clk) begin\n   if(!rst_n) begin out_vld<=0; pout<=0; end\n   else begin\n     out_vld <= in_vld;\n     ix = 9'd256 - {1'b0,dx};  iy = 9'd256 - {1'b0,dy};\n     sum = p00*ix*iy + p01*{1'b0,dx}*iy\n         + p10*ix*{1'b0,dy} + p11*{1'b0,dx}*{1'b0,dy};\n     pout <= (sum + 34'd32768) >> 16;\n   end\n end\nendmodule""")
code("""// 输出坐标 (u,v) 驱动查表：每拍推进一个输出像素\nmap_addr = v * OUT_W + u;\n{sx_q8, sy_q8} = map_rom_or_ddr[map_addr];\nx0 = sx_q8 >> 8;  y0 = sy_q8 >> 8;\ndx = sx_q8[7:0];   dy = sy_q8[7:0];\n// DDR 中一行 RGB888 地址示例：base + (y0*IN_W+x0)*3\n// 读取 (x0,y0),(x0+1,y0),(x0,y0+1),(x0+1,y0+1)，再送 bilinear_q8。""")
p('工程注意：上面 bilinear_q8 的乘法最好拆成 2 至 3 级寄存器并让综合器映射 DSP；输入和输出帧缓存采用 ping-pong 双缓冲；map 越界时直接输出黑色，并增加越界计数器。')
h('十一 可选高阶 双路并线或拼接处理',1)
p('若你说的“并线处理”是两路相机拼接：顺序必须是“每路先去畸变，再并线”。原始鱼眼图直接拼接会让重叠区无法对齐。基础拼接可先用固定偏移；高阶用单应矩阵 H 做坐标映射。')
code('[X  Y  1]^T = H * [x  y  1]^T，最后 x_out=X/W，y_out=Y/W')
p('H 是 3x3 矩阵，由两路重叠画面中的对应点在 PC/OpenCV 上离线求得。它把右相机坐标映射到公共画布。重叠区的最简单羽化公式为：')
code('Pout = alpha*PL + (1-alpha)*PR\nalpha = (overlap_right - x) / overlap_width')
p('PL、PR 是左右校正图像像素；x 是当前画布坐标。重叠区左边更信任左图，右边更信任右图。为避免除法，FPGA 中将 1/overlap_width 预先量化为常数，alpha 用 Q0.8。')
code("""// alpha_q8: 0..256，单通道拼接\nwire [15:0] mix = left_pix*alpha_q8 + right_pix*(9'd256-alpha_q8);\nassign out_pix = (mix + 16'd128) >> 8;""")
h('十二 仿真 测试和答辩证据',1)
table(['项目','怎么测','合格现象'],[
['标定质量','棋盘格角点重投影误差；保留标定图。','误差小且边缘角点不系统偏移；系数随重测稳定。'],
['直线校正','拍摄网格纸/门框；在相同位置对比校正前后。','原来弯曲的边线变直，尤其是四角。'],
['像素正确性','PC remap 输出与 FPGA 输出逐像素差分。','差异主要来自 Q8 量化，边界区域有明确掩码。'],
['实时性','输入 vs 与输出 vs 或帧号差测时延。','一帧一帧稳定输出，无跳帧、无撕裂、无错行。'],
['资源与带宽','记录 LUT、FF、BRAM、DSP、Fmax 和 DDR 读写。','时序裕量为正；带宽留余量。'],
], [1.1,2.8,2.4])
h('十三 建议的 6 周执行表',1)
table(['周次','主任务','必须交付'],[
['第 1 周','板卡视频环回；打印并采集棋盘格。','原图 HDMI 显示、15 张以上合格棋盘格。'],
['第 2 周','OpenCV 标定、生成 map；PC 验证。','K/dist、map_xy_q8.bin、校正前后图和误差记录。'],
['第 3 周','DDR 帧缓存、map 查表、最近邻版本。','FPGA 能输出明显校正图，哪怕画质尚未最佳。'],
['第 4 周','双线性插值、边界处理、原图/校正图切换。','B1-B6 全部完成，保存波形与资源报告。'],
['第 5 周','高分辨率/高帧率、稀疏 map、性能优化。','H1 或 H3 的量化对比数据。'],
['第 6 周','双路并线或在线配置；文档与视频。','H4/H5 演示，完整源码和 3 分钟答辩视频。'],
], [.8,3.15,2.35])
h('十四 知识来源与引用说明',1)
table(['内容','推荐来源','报告中的用途'],[
['相机内参、径向/切向模型、棋盘格标定','OpenCV 官方 Camera Calibration：https://docs.opencv.org/5.0/main_modules/calib.html','第六、七节的参数定义和畸变公式。'],
['Python 标定实践与至少约 10 张棋盘图的建议','OpenCV Camera Calibration Tutorial：https://docs.opencv.org/doc/doxygen/html/dc/dbb/tutorial_py_calibration.html','第六、九节的数据采集流程。'],
['映射表/插值工程思路','OpenCV remap 与 initUndistortRectifyMap API 文档；使用本报告第九节脚本可生成 FPGA 表。','离线生成 map，在线查表。'],
['赛题范围','2026 紫光同创赛道二命题文件/钉钉群材料。','基础/高阶要求以该文件最新版为准；请将其作为最终评分依据。'],
], [1.35,3.1,1.85])
h('十五 硬件设施清单与中等预算方案',1)
p('推荐主方案：盘古 100Pro+（MES2L676-100HP，PG2L100H-6IFBG676）+ 一颗 DVP 并行接口的 OV5640 广角/鱼眼相机 + 板载 HDMI 输入输出。选择 100H 而不是只用入门小板的原因，是本项目需要 DDR 帧缓存来支撑随机取样和双线性插值；100H 级平台的逻辑、DDR 和高速视频接口余量更适合后续做高分辨率和双路拼接。')
table(['类别','推荐型号或规格','数量','预算 单价','用途与选型理由'],[
['核心 FPGA 板','盘古 100Pro+ MES2L676-100HP，PG2L100H-6IFBG676','1','约 3,200 至 4,200 元','主控。优先购买带 DDR3、HDMI 输入/输出、JTAG、电源和完整资料的套装；不要只买裸芯片。'],
['主摄像头','OV5640 500 万像素 DVP 并行接口，广角 130 度或鱼眼 180 度，带匹配转接板','1','约 160 至 260 元','故意选择有明显畸变的镜头，才便于展示校正效果。必须是 DVP 并行接口，不能买 USB/UVC 或 MIPI-only 版。'],
['板级转接','与盘古 100Pro+ 引脚定义匹配的 OV5640 摄像头扩展板/40 pin 转接板','1','约 120 至 220 元','解决 FPC 排线、3.3V 电平、XCLK、SCCB 与 DVP 引脚对接；下单前向板卡卖家确认。'],
['显示和线材','1080P HDMI 显示器或现有显示器、HDMI 线 2 根','1 套','约 300 至 900 元','一根作为输入测试源，一根用于校正结果输出；显示器可复用则不重复采购。'],
['输入测试源','HDMI 采集棒或 Raspberry Pi/笔记本 HDMI 输出','1','约 180 至 350 元','用于播放棋盘格、网格、录像，避免把摄像头调试与算法调试混在一起。'],
['存储与备份','MicroSD 64GB U3 或 U 盘 64GB','1','约 50 至 80 元','保存原始/校正视频、标定照片、bitstream 与答辩备份。'],
['调试工具','USB 转串口、8 通道逻辑分析仪、万用表','1 套','约 200 至 380 元','抓 SCCB/I2C 配置、视频同步和帧号；比只看显示器更易定位故障。'],
['供电与结构','12V 2A 备用电源、三脚架/固定支架、杜邦线、棋盘格打印与泡沫板','1 套','约 250 至 400 元','防止演示时断电和相机位姿变化；棋盘格需要平整固定。'],
], [1.0,2.35,.45,.95,1.55])
p('标准单路方案的设备总预算约为 4,500 至 6,800 元；如果已有显示器/电脑，通常落在 4,200 至 5,500 元。该预算把板卡、真实广角相机、显示、测试输入、调试和备用供电都算入，不会因省掉帧缓存、相机转接或调试工具而使功能缺失。板卡实际成交价和相机接口版本差异很大，采购前应按“接口兼容性优先、价格其次”向卖家确认。')
h('十六 高阶双目并线的追加硬件',1)
table(['新增件','规格','数量','增量预算','何时购买'],[
['第二摄像头','与主摄像头完全相同的 OV5640 DVP 广角/鱼眼版本','1','160 至 260 元','完成单路校正、存储与显示稳定后再买；不同镜头混用会增加标定复杂度。'],
['双目转接','双路 DVP 摄像头扩展板，或两套已验证的独立接口转接','1','180 至 350 元','只有板卡有足够并行 IO、时钟和两路 SCCB 时才选；购买前核对原理图。'],
['机械固定','双相机刚性支架，基线可调但锁紧后不移动','1','100 至 220 元','并线/拼接需要固定相对姿态；手持两颗相机无法稳定标定。'],
['可选存储升级','外接 DDR/更大容量板卡仅在板载 DDR 不足时考虑','0 或 1','0 至 800 元','先测带宽与帧缓存需求，避免无依据扩展硬件。'],
], [1.1,2.65,.5,1.0,1.55])
p('双目高阶方案在标准单路基础上增加约 450 至 1,100 元，完整预算约 5,000 至 7,900 元。它的增益是可演示“去畸变后并线拼接”，但不是基础闭环的前置条件。')
h('十七 采购验收与接口核对表',1)
table(['采购前必须核对','正确要求','错误或风险'],[
['FPGA 型号','丝印为 PG2L100H，且板卡资料确认 DDR3、HDMI IN、HDMI OUT、JTAG 可用。','把“盘古100K/100H”当成唯一型号，不核对具体封装、底板版本和接口。'],
['相机数据接口','DVP 并行：D0-D7、PCLK、VSYNC、HREF、XCLK、SCCB/I2C；优先 3.3V IO。','USB 摄像头不能直接接 FPGA IO；MIPI CSI 需专用 D-PHY/转接，基础项目不建议。'],
['镜头类型','130 度广角或 180 度鱼眼，有清晰的 FOV 与排线规格。','购买“无畸变 100 度”镜头后，几乎无法体现项目的校正价值。'],
['分辨率与帧率','先锁定 1280x720@30fps；跑通后再挑战 60fps/1080p。','同时改摄像头分辨率、时钟、DDR 与算法，问题无法定位。'],
['板级资料','原理图、管脚约束、摄像头例程、DDR/HDMI 例程、PDS 版本。','只买硬件不确认例程和引脚定义，后续接线风险极高。'],
], [1.3,2.75,2.75])
p('硬件信息来源：紫光同创官方 Logos-2 开发板目录列有 PG2L100H 盘古 100K 开发板；盘古 100Pro+ 资料标明 MES2L676-100HP 使用 PG2L100H-6IFBG676。该板的 HDMI 输入资料说明采用 MS7200 接收器。OV5640 选型采用公开 500 万像素 DVP 广角/鱼眼模组，选择 DVP 而非 USB/MIPI 是为了直接接入 FPGA 并行 IO。参考链接：https://www.pangomicro.com/product/logos_family/195.html；https://www.meyesemi.com/upload/202506161411078.pdf；https://www.superfae.cn/productinfo/788060.html')
p('特别提醒：不要把 OpenCV 在 PC 上直接跑出的校正结果当成最终作品。它应仅作为“标定与生成 LUT 的工具”和 FPGA 输出的黄金参考；答辩演示必须由 FPGA 端读取映射、取四邻像素并完成插值。')
f=sec.footer.paragraphs[0];f.alignment=WD_ALIGN_PARAGRAPH.CENTER;r=f.add_run('2026 FPGA 紫光同创赛道二 畸变图像校正详细实施报告');r.font.size=Pt(8);r.font.color.rgb=RGBColor(90,90,90)
d.core_properties.title='2026 FPGA 紫光同创赛道二畸变图像校正详细实施报告';d.save(FN);print(FN)
