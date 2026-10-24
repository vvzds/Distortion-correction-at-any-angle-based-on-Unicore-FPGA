"""Collect strict pass gates and produce the reviewable step-1/2 delivery."""
import hashlib
import json
import re
import zipfile
from pathlib import Path
from prepare_and_check import ROOT, digest, verify_manifest

def main():
    assert verify_manifest(ROOT/'received/G4')==256
    integration=ROOT/'received/integration/integ_ws_regression_pkg_20261019'
    verify_manifest(integration,integration.parent)
    for name in ('undistort_map.v','undistort_core.v','undistort_bilinear.v','undistort_line_cache.v'):
        assert digest(ROOT/'received/G4/source/rtl'/name)==digest(integration/'source/rtl'/name)
    definitions={
        'source_words':('logs/source_words.log',r'SOURCE_WORDS PASS pixels=4147200'),
        'uart':('logs/uart.log',r'UART PASS .*updates=2'),
        'boundary':('logs/boundary.log',r'BOUNDARY PASS checks=32'),
        'bilinear':('logs/bilinear.log',r'=== ALL TESTS PASSED \(err=0\) ==='),
        'cache':('logs/cache.log',r'=== ALL TESTS PASSED \(err=0\) ==='),
        'map':('logs/map_full.log',r'MAP PASS pixels=2073600 err=0'),
        'identity':('logs/core_identity.log',r'CORE PASS mode=0 pattern=1 slot=0 pixels=2073600 err=0'),
        'real_highfreq':('logs/core_real_highfreq.log',r'CORE PASS mode=1 pattern=1 slot=3 pixels=2073600 err=0'),
    }
    results={}
    for name,(filename,gate) in definitions.items():
        p=ROOT/filename;text=p.read_text(encoding='utf-8-sig')
        assert re.search(gate,text),f'{name}: missing pass gate'
        assert not re.search(r'FAIL|FATAL|MISMATCH|TIMEOUT|ERROR:',text),f'{name}: failure marker'
        result={'pass':True,'log':filename,'log_sha256':digest(p)}
        if name in ('identity','real_highfreq','real_smooth'):
            match=re.search(r'cycles=(\d+) cpp=([\d.]+) model_fps_125MHz=([\d.]+) line_loads=(\d+) hits=(\d+) first_read=(\d+) last_read=(\d+) minrow=(\d+) maxrow=(\d+)',text)
            assert match
            for key,value in zip(('cycles','cpp','model_fps_125MHz','line_loads','hits','first_read','last_read','minrow','maxrow'),match.groups()):
                result[key]=float(value) if key in ('cpp','model_fps_125MHz') else int(value)
            assert result['minrow']>=0 and result['maxrow']<=1079
        results[name]=result
    metrics=json.loads((ROOT/'reports/offline_metrics.json').read_text())
    encoding=json.loads((ROOT/'parameters/parameter_encoding.json').read_text())
    source_hashes={p.relative_to(ROOT).as_posix():digest(p) for p in sorted(ROOT.rglob('*'))
                   if p.is_file() and (p.suffix in ('.py','.v','.vh','.ps1','.csv','.bin')
                   or p.name=='标定结果说明(1).md') and '__pycache__' not in p.parts}
    (ROOT/'reports/inputs_sha256.json').write_text(json.dumps(source_hashes,indent=2,ensure_ascii=False),encoding='utf-8')
    (ROOT/'reports/verification_summary.json').write_text(json.dumps(dict(
        date='2026-10-22',baseline='G4 (user confirmed)',simulator='Icarus Verilog 12.0 development build',
        image=[1920,1080],capture_and_hdmi_target_fps=30,affine_enabled=False,gamma_enabled=False,
        tests=results,offline_metrics=metrics,production_RTL_modified=False,
        board_tested=False,bitstream_generated=False,uart_sent_to_board=False),indent=2),encoding='utf-8')
    lines=['# 标定参数接入与 G4 核心仿真核对报告','',
        '日期：2026-10-22。用户确认基线为 G4。**第 1、2 步通过本轮离线功能检查**；保持 1920×1080@30fps 采集与 HDMI 图像配置。未生成新位流、未发送板端 UART、未烧录，未更改生产 RTL、冻结接口或摄像头/显示时序。','',
        '## 1. 参数包','',
        'Brown4，k3=0，K_out=K_in。输入来自归档的《标定结果说明(1).md》。每项按 Decimal 最近值（half-even）量化为有符号 Q16.16，再与冻结 uart_host_tool 的编码器逐字节互证。输入和量化后值均通过 G02，参数顺序、负数补码及小端字节均已检查。','',
        '|参数|有符号整数|32bit 补码|解码值|','|---|---:|---|---:|']
    for p in encoding['parameters']:
        lines.append(f"|{p['name']}|{p['signed_integer']}|`{p['hex']}`|{p['decoded']:.12f}|")
    lines+=['','0x01 负载 32B、完整帧 37B，校验和 **A0**：','',
        '```text',encoding['cmd01_hex'],'```','',
        '生成 real/identity 两组 `.bin`、`.hex`、CSV 与 `calibration_q16.vh`；仿射关闭、Gamma 关闭。identity 保留真实 K，只把四个畸变系数归零。常数文件不等于已经固化或下发。','',
        '## 2. 数学参考与定点误差','',
        '独立 NumPy float64 参考直接实现 Brown4 正向畸变公式用于逆向采样：给定校正输出像素，以输出 K 归一化，施加畸变后到原始畸变图取样；不是对输入像素正向撒点，也不是解反函数。保持左上原点和 p1/p2 符号。参考分别采用原浮点参数与 UART 量化参数，不复用 RTL 算术步骤。','',
        '另有与实际 RTL 逐位核对的整数诊断模型，用于定位截断/插值差异；该模型与 RTL 相等只构成一致性证据，精度结论来自独立浮点参考。全帧 2,073,600 点检查，RGB565 按通道插值（禁止直接对 16bit 编码做标量插值）。','',
        '|比较|最大二维偏差(px)|二维 RMS(px)|','|---|---:|---:|']
    for key,label in [('quantized_vs_original','参数量化浮点 vs 原浮点'),('arithmetic_vs_quantized','定点运算 vs 量化参数浮点'),('total_vs_original','最终定点 vs 原浮点')]:
        m=metrics[key];lines.append(f"|{label}|{m['max_euclidean_px']:.9f}|{m['rms_euclidean_px']:.9f}|")
    lines+=['','最终定点相对原浮点的单轴最大偏差：x %.9fpx、y %.9fpx。两种测试图案（分段渐变/高频非对称）均为每通道最大 1 LSB、≤1 LSB 占比 100%%，满足冻结 max≤2 LSB、≤1 LSB 占比≥99.5%%。'%(metrics['total_vs_original']['max_abs_x_px'],metrics['total_vs_original']['max_abs_y_px']),'',
        '## 3. 本机真实 RTL 实跑','',
        '采用 Icarus Verilog 12.0 开发版实际编译和运行；不是本轮 ModelSim 10.7 实跑。G4 四核原件与设计方集成回归包逐字节相同，G4 清单 256 件通过。未降低图像尺寸；core 使用 SIM_MODE=0、LINES_PER_SET=2（共四行缓存）。','',
        '|用例|检查范围|结果|','|---|---|---|',
        '|DDR源图查表|两图案共4,147,200像素与原过程模型逐像素一致，含内存行翻转及256bit字内顺序|PASS|',
        '|UART|真实 125MHz/115200 8N1 串行输入；两组37B帧解码；busy期间旧组保持、间隙后原子更新|PASS|',
        '|map|真实参数全帧2,073,600坐标逐位核对，四原始槽地址范围|PASS|',
        '|boundary|32点，正负40.5及±4096像素压力测试，四边钳位、rowB=0|PASS|',
        '|bilinear|G4原TB，3个定向及1000随机四邻域/权重输入，独立real公式|PASS|',
        '|cache|G4原TB，块跨界/末像素/同一行双取样/交替流水及错误last等72项|PASS|',
        '|identity core|原始槽0，完整2,073,600输出，内容/坐标/标志逐像素精确|PASS|',
        '|real core 高频|原始槽3，完整2,073,600输出，内容/坐标/行翻转/标志逐像素精确|PASS|',
        '|分段渐变浮点对照|完整2,073,600点定点与两组独立浮点插值对照，不另计为完整core实跑|PASS|','',
        '每次 core 检查请求 len=119、行首960字对齐、槽匹配、单在途、返回120拍、停顿时请求保持、load_error=0、源帧释放晚于输出/返回排空、发布像素统计和首尾行标志。DDR 服务模型含首拍延迟和返回有效拍间隙。','',
        '屏幕行 j=floor(sy)，读 rowA=1079−j、rowB=max(rowA−1,0)；实际每次 sample_dispatch 与独立期望行号一致。源数据模型用 y_screen=1079−y_mem 填充，输出按 y_mem 升序；恒等测试首读0末读1079，HDMI按1079→0读取后方向保持。完整两邻域、四原始槽离线地址检查无负行回绕/越槽；校正槽4–7的顺序写与显示翻转仅做冻结公式核对，本轮未运行真实DDR写回/HDMI整机联仿。','',
        '真实参数的全帧源坐标位于 x=[99.254242,1768.552109]、y=[28.875580,1057.580551]，一般不会触发钳位；因此额外边界测试独立列出，不能把真实参数未触边等同于验证过钳位。','',
        '## 4. 周期与30fps边界','',
        '|完整core用例|总周期|周期/输出像素|125MHz模型帧率|行加载数|','|---|---:|---:|---:|---:|']
    for name,label in [('identity','恒等'),('real_highfreq','真实参数·高频')]:
        r=results[name];lines.append(f"|{label}|{r['cycles']}|{r['cpp']:.6f}|{r['model_fps_125MHz']:.6f}|{r['line_loads']}|")
    lines+=['','**本轮真实参数在 G4 上功能通过，但本模型下的新校正帧率明确未达到30fps。** 以上为简化 DDR 服务模型和125MHz时钟下单帧核心计算值，未包含真实 DDR 仲裁/校正槽排空/显示切槽，不能当作实板发布率或帧率下界。真实参数单输出行最多跨73个源行，超过四行缓存容量，会重载。69,916次行加载对应8,389,920个256bit返回有效拍，单这些拍数就超过30fps整帧预算4,166,667周期，不能只靠保持HDMI为30Hz来获得30个新校正帧。HDMI可以30Hz重复显示最新完成帧，摄像头采集配置仍保持30fps；缓存/访存优化属于另一步工作，本轮未单方面重构。','',
        '## 5. 交付边界与下一步','',
        '- 本轮可进入“具备真实校正核的整机集成、恒等参数先行、再真实参数”的下一阶段；需用户安排后执行第3、4步，不能下载空hook宿主冒充完整校正系统。',
        '- 棋盘/直线实拍效果、边缘质量、随机彩点、整机实际校正发布率、连续运行稳定性均未验收。标定最外侧/四角覆盖限制仍保留。',
        '- G4目标时序尚未闭合的既有问题未由本次数值功能测试解决，不将G6某个种子结果移植为G4时序结论。',
        '- 工具启动阶段曾遇到Icarus长路径兼容问题，使用临时subst映射解决；runner的PowerShell数组拼接问题也已修复。首轮真实参数全帧因DDR模型逐返回拍计算16个图案像素过慢，由本方停止，归档在logs/startup_and_performance，不计PASS；改为256bit源图查表后重新完整运行。查表的两个完整源图与原过程式模型另经4,147,200像素逐点等价检查。被测RTL、服务节奏、误差阈值、像素数和超时不变。',
        '- 必需的真实高频全帧通过后，停止了已排队启动的可选分段渐变core重复帧；其未完成运行归档、不计PASS。渐变图案只有全帧独立浮点/定点对照结论；后续需要时可用-Cases real_smooth单独重跑。',
        '- `reports/verification_summary.json` 和输入/日志哈希提供机器可读证据；`run_verification.ps1`可复跑。参数包ZIP只含参数和说明，复现ZIP包含原件/脚本/日志；大体积向量和NPZ留在本地、由生成器重建。','',
        '若无错误不进行回复；仅有技术问题时回传。']
    (ROOT/'验证报告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for filename,selector in [('FPGA参数包_1080p30_20261022.zip',lambda p:p.parts[0]=='parameters' or p.name in ('README.md','验证报告.md')),
                               ('G4标定参数仿真核对_复现包_20261022.zip',lambda p:p.parts[0] not in ('vectors',) and p.suffix!='.vvp' and '__pycache__' not in p.parts)]:
        target=ROOT.parent/filename
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for p in sorted(ROOT.rglob('*')):
                rel=p.relative_to(ROOT)
                if p.is_file() and selector(rel):archive.write(p,rel.as_posix())
        with zipfile.ZipFile(target) as archive:assert archive.testzip() is None
        target.with_suffix(target.suffix+'.sha256').write_text(digest(target)+'  '+target.name+'\n',encoding='utf-8')
    print('ALL 8 required verification gates passed; reports and delivery archives generated.')

if __name__=='__main__':main()
