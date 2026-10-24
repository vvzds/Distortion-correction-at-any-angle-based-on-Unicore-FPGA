# A02-CW1 / A03-CW2–CW4

结论：离线证据核查和最小清理候选完成；原冻结告警与板级适用性没有被整体关闭，候选不供上板。

## 原始事件与清理范围

复核258份来源、96阶段、2288条原始C级事件；原G7综合38=36共享引脚+UART两条，G8综合46=原38+8条STA传播提示。保留候选/seed/阶段/重复次数，不以跨阶段相加充当独立问题数。原38逐项台账仍是原冻结基线，候选结果不回写原件。

独立 G8 宿主只改两份文件：
- top 删除三条无消费者debug声明（18位），并移除没有消费者的CMOS1 data/href/pclk/vsync四个输入声明（11位）。这些标识符在旧top各只出现于声明；CMOS2 RAW→RGB、DDR、校正、HDMI主动逻辑和所有子模块源码保持字节相同。
- FDC 删除这11个已移除端口的55条属性；UART TX增加8mA/SLOW。CMOS1 SCCB/复位/初始化保留。全部时钟、输入输出延时和false_path原句未改。

这是外部top端口减去11个无用输入的独立候选，不是冻结接口的原地修改。若后续需要CMOS1像素采集，应保留原完整宿主；本候选只适合单路CMOS2。diff见 evidence/review_evidence/cw_cleanup.diff。

UART依据：厂商 uart_test 原FDC TX=C24/RX=B24，LVCMOS33，TX8mA/SLOW；厂商远程升级例程12mA/SLOW是另一配置，未混用。清理后的PRR确认C24/BANKL3/3.3/LVCMOS33/8/SLOW。未测真实负载/电压，因此只完成显式约束候选闭环。A01 AB未复制上述UART位置。

## 本机一次 seed2 实跑

SP6.1 build138931，进程退出0，输入前后未变；无gen_bit_stream。完整原件见 runs/cw_cleanup_seed2，进程记录见 evidence/cw_cleanup_evidence。

|阶段|冻结G8 seed2|清理候选|结果|
|---|---:|---:|---|
|compile|18|0|18条debug告警消失|
|synthesize|46|44|UART DRIVE/SLEW两条消失；36共享+8STA保留|
|place_route|51|38|11条CMOS1悬空与UART两条消失；36共享+2SRB保留|
|report_timing|32|32|未抑制STA传播提示|

CSV四角：SetupSlow −0.640、SetupFast 1.499、HoldSlow 0.138、HoldFast 0.099ns；holdfix SetupSlow −0.632ns/TNS−59.311/115端点，方向均FAIL。器件LUT11467、模块顶层11466，仍差1；FF16139、APM107、DRM29.5。cache16仍超过最终≤12。新结果不能混入原G8八种子，也不能从一次结果或SP差异推断改动改善了时序。

## SCCB时钟、扇出、例外与复位

原生rtr.db明确：sccb1/2的主时钟都是clk_25M，目标已解析到对应clock_20k/opit_0_inv/Q，周期96969.6000ns；Clock Load分别34/33，Non-clock Load均7。这说明原get_nets已解析到分频FF输出，暂无依据仅将其改写为get_pins就能解决告警。

原G8 seed2 routed.v独立提取18,919个原语实例。直接连接中clock_20k分别有33/32个CLK端口，另各有ROM的CLKA/CLKB、反馈逻辑和SCL输出逻辑。该直接引脚计数不与STA的“Clock Load”混同。四个唯一non_unate路径中，两个是clock_20k反馈逻辑至自己的D输入，两个位于外部SCL组合逻辑；全16轮所有576条STA-3003原事件另行保留，不能把seed2的连接结论自动推广到所有种子。

原生 exception_report 的两角setup/hold各命中两个initial_enable_sync首级D；recovery/removal各命中两个camera_reset_sync首级RS，原FDC第991行。记录为真实STA报告命中，不用源码猜测；报告已列路径不等同于超出report容量的全图穷举。SCCB内部同步释放后的recovery/removal在本轮报告中无违规；从sys_clk到首级RS的例外不等于首级异步解除已完成物理验证。

原语明确gopSRL2、RS_MODE=ASYNC，两路reset和enable的SRL打包/RS链属性已记录。安装目录可检索的明文Verilog未找到gopSRL2行为模型，因此没有伪造等效模型冒充厂商原语仿真。RTL定向测试相位3/47/93通过，每次含中途异步复位、首笔NACK及重试、263次完整32bit+4ACK事务、配置完成、两慢拍复位释放；另以原参数测得分频2400输入拍。协议测试加速I2C_HALF_PERIOD=4，仿真输入周期10ns；这不是声称在实板24.75MHz完成原语时序验收。

源/时钟查询的@tcicmdresult句柄不是对象清单，主时钟/实际目标证据取自原生rtr.db。没有扩大false_path、删有效时钟或压低warning级别。SRB/原语复位语义、同步器保护/放置及实际复位波形仍交二号B02/B04和设计方审阅；如需clock-enable架构，另交方案裁定。

## 板级剩余条件

36条C1逐脚表已填当前LOC/工具电气/手册检索页/缺失项，见 evidence/review_evidence/C1_36pin_board_ledger.md。用户已给出MES2L676、BASE V1.2，厂商手册提供供电与上电说明；仍缺准确封装配置复用表、原理图逐脚网名、实际启动模式和供电闭环。

清理候选原生检查仍有37个无input delay、90个无output delay端口，包含UART/控制与DDR相关接口；逐项原生清单保留，不能用数量直接判全部有错或全部豁免。需按真实外接器件及专用DDR语义分类确认，不填猜测值。
