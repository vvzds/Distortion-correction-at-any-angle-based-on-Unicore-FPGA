from pathlib import Path
import hashlib,json,shutil
W=Path(__file__).resolve().parent
R=Path('C:/Users/叶翔/Documents/Codex/fpga-main')
P=Path('D:/FPGA PDS/yx/DCSjingtaijiaozheng')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources={
 'reference/param_mgr.v':R/'source/rtl/param_mgr.v',
 'reference/param_mgr_tb.v':R/'sim/param_mgr_tb.v',
 'reference/corr_top.v':P/'01_project/top_recovery/source/rtl/corr_top.v',
 'reference/UART参数协议规格_V1.2.md':R/'uart_host_tool/UART参数协议规格_V1.2.md',
 'reference/uart_tool_tlimfix.py':P/'04_uart_tool/uart_tool.py',
}
for p in (P/'03_parameters/parameters').iterdir():
 if p.is_file():sources['reference/parameters/'+p.name]=p
manifest=[]
for name,p in sources.items():
 q=W/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
 manifest.append(dict(path=name,source=str(p),sha256=sha(q),bytes=q.stat().st_size))
bit=P/'01_project/top_recovery/generate_bitstream/hdmi_ddr_ov5640_top.sbit'
manifest.append(dict(path='EXTERNAL_BITSTREAM',source=str(bit),sha256=sha(bit),bytes=bit.stat().st_size))
assert sha(R/'source/rtl/param_mgr.v')==sha(P/'01_project/top_recovery/source/rtl/param_mgr.v')
(W/'input_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
# 复用旧TB的UART驱动；新增判定覆盖全输出总线与全部G02边界。
s=(W/'reference/param_mgr_tb.v').read_text(encoding='utf-8')
s=s[:s.index('    //----------------------------------------------------------\n    // Main test sequence')]
s=s.replace('module param_mgr_tb;','module param_mgr_extended_tb;')
a=s.index('    always @(posedge clk or negedge rst_n) begin\n        if (!rst_n) begin upd_cnt')
b=s.index('    //----------------------------------------------------------',a)
s=s[:a]+'''    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) upd_cnt <= 0;
        else if (o_param_updated) upd_cnt <= upd_cnt + 1;
    end
    // 在NBA之后核对全部输出；不允许busy拍更新或无脉冲静默修改。
    wire [6594:0] all_live = {o_fx,o_fy,o_cx,o_cy,o_k1,o_k2,o_p1,o_p2,
        o_a11,o_a12,o_a21,o_a22,o_tx,o_ty,o_aff_en,o_params_valid,o_gamma_en,o_gamma_lut};
    reg [6594:0] previous_live;
    reg busy_at_edge;
    always @(posedge clk) begin
        busy_at_edge = i_rect_busy;
        #1;
        if (rst_n) begin
            if (busy_at_edge && (o_param_updated || all_live !== previous_live)) begin
                $display("FAIL: live group changed while busy"); err=err+1;
            end
            if (all_live !== previous_live && !o_param_updated) begin
                $display("FAIL: live group changed without update flag"); err=err+1;
            end
        end
        previous_live = all_live;
    end

'''+s[b:]
s+='''
    reg signed [31:0] words [0:13];
    reg signed [31:0] low_bound [0:13];
    reg signed [31:0] high_bound [0:13];
    reg [6594:0] held;
    integer n,j,k,before_count,expected_valid;
    task defaults;
        integer t;
        begin
            for(t=0;t<14;t=t+1) words[t]=0;
            words[0]=32'sh03e80000; words[1]=32'sh03e80000;
            words[2]=32'sh03c00000; words[3]=32'sh021c0000;
            words[8]=32'sh00010000; words[11]=32'sh00010000;
        end
    endtask
    task send_words;
        input integer affine;
        integer t,offset;
        begin
            offset=affine ? 8 : 0;
            frame_len=affine ? 25 : 32;
            for(t=0;t<(affine ? 6 : 8);t=t+1) begin
                frame_buf[t*4]=words[t+offset][7:0];
                frame_buf[t*4+1]=words[t+offset][15:8];
                frame_buf[t*4+2]=words[t+offset][23:16];
                frame_buf[t*4+3]=words[t+offset][31:24];
            end
            if(affine) frame_buf[24]=1;
            send_frame(affine ? 8'h02 : 8'h01,affine ? 8'd25 : 8'd32,0);
        end
    endtask
    task swap_and_check;
        input integer legal;
        begin
            @(negedge clk); i_rect_busy=0;
            repeat(5) @(negedge clk);
            if(o_params_valid !== (legal!=0)) begin
                $display("FAIL: boundary index=%0d value=%h valid=%b expected=%0d",n,words[n],o_params_valid,legal);
                err=err+1;
            end
            if ({o_fx,o_fy,o_cx,o_cy,o_k1,o_k2,o_p1,o_p2,o_a11,o_a12,o_a21,o_a22,o_tx,o_ty}
                !== {words[0],words[1],words[2],words[3],words[4],words[5],words[6],words[7],
                     words[8],words[9],words[10],words[11],words[12],words[13]}) begin
                $display("FAIL: entire scalar group mismatch"); err=err+1;
            end
            i_rect_busy=1;
        end
    endtask
    initial begin
        rst_n=0; repeat(10) @(negedge clk); rst_n=1;
        defaults;
        send_words(0); send_words(1);
        swap_and_check(1);
        $display("E0 full group initial load: PASS");
        low_bound[0]=32'sh00800000; high_bound[0]=32'sh7fffffff;
        low_bound[1]=32'sh00800000; high_bound[1]=32'sh7fffffff;
        low_bound[2]=0; high_bound[2]=32'sh077f0000;
        low_bound[3]=0; high_bound[3]=32'sh04370000;
        for(n=4;n<14;n=n+1) begin
            if(n<6) high_bound[n]=32'sh00008000;
            else if(n<8) high_bound[n]=32'sh0000028f;
            else if(n<12) high_bound[n]=32'sh00020000;
            else high_bound[n]=32'sh10000000;
            low_bound[n]=-high_bound[n];
        end
        // 每个字段逐一测两端点及外侧1LSB；fx/fy上端外溢成负数仍应非法。
        for(n=0;n<14;n=n+1) begin
            for(j=0;j<4;j=j+1) begin
                defaults;
                case(j)
                    0: words[n]=low_bound[n];
                    1: words[n]=high_bound[n];
                    2: words[n]=low_bound[n]-1;
                    3: words[n]=high_bound[n]+1;
                endcase
                send_words(0);send_words(1);
                swap_and_check(j<2);
            end
        end
        $display("E1 G02 all 14 fields, endpoints and 1LSB outside (56): done");
        defaults;send_words(0);send_words(1);swap_and_check(1);
        // 连续影子写入覆盖旧值，busy期间保持全部输出包括768字节LUT。
        held=all_live; before_count=upd_cnt;
        words[0]=32'sh04000000;send_words(0);
        words[0]=32'sh05000000;send_words(0);
        for(n=0;n<3;n=n+1) begin
            for(k=0;k<256;k=k+1) frame_buf[k]=(k+n*37)&255;
            frame_len=256;send_frame(8'h03,n,0);
        end
        repeat(10) @(negedge clk);
        if(all_live !== held || upd_cnt!=before_count) begin
            $display("FAIL: busy group was not held");err=err+1;
        end
        n=0;swap_and_check(1);
        if(upd_cnt!=before_count+1) begin $display("FAIL: aggregate swap count");err=err+1;end
        for(n=0;n<3;n=n+1) for(k=0;k<256;k=k+1)
            if(o_gamma_lut[(n*256+k)*8+:8] !== ((k+n*37)&255)) begin
                $display("FAIL: LUT channel=%0d index=%0d",n,k);err=err+1;
            end
        $display("E2 all 768 LUT entries and scalar group atomic hold/swap: done");
        held=all_live;before_count=upd_cnt;
        @(negedge clk);i_rect_busy=0;
        frame_len=4;for(k=0;k<4;k=k+1)frame_buf[k]=0;
        frame_buf[0]=1;send_frame(8'h04,4,1);
        frame_len=0;send_frame(8'h03,3,0); // 非法通道，无负载
        send_frame(8'h02,24,0); // 非法长度，无负载
        repeat(20) @(negedge clk);
        if(all_live !== held || upd_cnt!=before_count) begin
            $display("FAIL: rejected frame altered live group");err=err+1;
        end
        $display("E3 checksum/length/channel rejection: done");
        // 新分发与旧dirty切换同拍：旧组先切、新组下一拍切，不丢新命令。
        i_rect_busy=1;words[0]=32'sh06000000;send_words(0);
        words[0]=32'sh07000000;
        fork
            send_words(0);
            begin
                @(posedge dut.disp_valid);@(negedge clk);i_rect_busy=0;
                @(negedge clk);
                compare32("E4 old shadow",o_fx,32'h06000000);
                compare32("E4 update old",{31'd0,o_param_updated},1);
                @(negedge clk);
                compare32("E4 new shadow",o_fx,32'h07000000);
                compare32("E4 update new",{31'd0,o_param_updated},1);
            end
        join
        repeat(8) @(negedge clk);
        if(dut.sh_dirty!==0) begin $display("FAIL: dirty not cleared");err=err+1;end
        $display("E4 coincident dispatch/swap: two adjacent update cycles, latest value retained");
        if(err==0) $display("=== ALL TESTS PASSED (err=0) ===");
        else $display("=== TEST FAILED: err=%0d ===",err);
        $finish;
    end
endmodule
'''
(W/'tb').mkdir(exist_ok=True)
(W/'tb/param_mgr_extended_tb.v').write_text(s,encoding='utf-8')
print('Prepared manifest and extended TB')
