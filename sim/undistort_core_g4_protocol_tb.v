`timescale 1ns/1ps
// G4专项：内部调度条件注入，独立检查地址、授权、全速返回及复位。
// 不替代原冻结全帧/real golden。MODE=1覆盖SIM入口。
module undistort_core_g4_protocol_tb;
    parameter MODE=0;
    parameter FAULT=0;
    reg clk=0,rst_n=0,gnt=0,vld=0,last=0,start=0;
    reg [255:0] data=0;
    wire [23:0] addr;
    wire [6:0] len;
    wire req;
    wire [31:0] loads,hits,pixels,frames;
    wire busy,hold_req,rel,pix_valid,sop,eop,sof,eof;
    wire [15:0] pixel;
    reg ha=0,hb=0,ph=0;
    integer err=0,fd,cases=0,slot_no,row_no,kind,delay_no,stall_no;
    integer j,k,bank_saved,loads_saved,reset_phase,negatives=0;
    integer clock_ticks=0,accepted_tick;
    integer error_cases=0;
    reg gap_enable=0;
    reg [10:0] row_saved;
    reg [23:0] expected,old_addr;
    reg [10:0] boundaries [0:2];
    always #4 clk=~clk;
    always @(posedge clk) clock_ticks=clock_ticks+1;
    undistort_core #(.SIM_MODE(MODE)) dut(
        .clk(clk),.rst_n(rst_n),.i_fx(32'sd65536000),.i_fy(32'sd65536000),
        .i_cx(32'sd62914560),.i_cy(32'sd35389440),
        .i_k1(32'sd0),.i_k2(32'sd0),.i_p1(32'sd0),.i_p2(32'sd0),
        .i_aff_a11(32'sd65536),.i_aff_a12(32'sd0),
        .i_aff_a21(32'sd0),.i_aff_a22(32'sd65536),
        .i_aff_tx(32'sd0),.i_aff_ty(32'sd0),.i_aff_en(1'b0),
        .i_frame_start(start),.o_frame_busy(busy),.o_corr_src_hold_req(hold_req),
        .i_corr_src_hold_gnt(1'b0),.i_corr_src_slot(2'd0),.o_corr_src_rel(rel),
        .o_corr_rd_addr(addr),.o_corr_rd_len(len),.o_corr_rd_req(req),
        .i_corr_rd_gnt(gnt),.i_corr_rd_vld(vld),.i_corr_rd_data(data),.i_corr_rd_last(last),
        .o_pix_vld(pix_valid),.o_pix(pixel),.o_sop(sop),.o_eop(eop),.o_sof(sof),.o_eof(eof),
        .o_stat_frame_cnt(frames),.o_stat_line_loads(loads),
        .o_stat_line_hits(hits),.o_stat_pix_cnt(pixels)
    );
    task check;
        input condition;
        input [639:0] message;
        begin
            if(condition!==1'b1) begin
                err=err+1;
                if(err<100) $fdisplay(fd,"FAIL mode=%0d case=%0d %0s",MODE,cases,message);
            end
        end
    endtask
    // 独立违规判据；负向注入必须被识别，不允许把非法组合作为有效访问。
    function bad_prepare;
        input req_seen,begin_seen;
        input [31:0] before_count,after_count;
        begin bad_prepare=req_seen || begin_seen || before_count!=after_count;end
    endfunction
    task reset_dut;
        begin
            @(negedge clk);rst_n=0;gnt=0;vld=0;last=0;start=0;ha=0;hb=0;ph=0;
            #1;check(!req && !dut.cache_load_begin && loads==0 && !busy,"reset clears request/state");
            repeat(2) @(negedge clk);
            rst_n=1;
        end
    endtask
    task prepare;
        input integer sl,rr,which;
        begin
            reset_dut;
            // MODE=0使用真实RUN入口；MODE=1使用SIM_RUN。
            dut.state=(MODE!=0)?4'd7:4'd4;
            dut.o_frame_busy=1;dut.source_slot=sl;
            dut.fifo_rd=0;dut.fifo_wr=4;dut.fifo_count=4;
            dut.inflight_count=0;dut.gen_done=1;dut.sample_phase=0;
            dut.consume_x=0;dut.consume_y=0;dut.sim_x=0;
            dut.identity_mode=0;dut.prefetch_active=0;
            dut.replace_cursor=sl;dut.o_corr_rd_addr=24'hfabcde;
            dut.sim_a=rr;dut.sim_b=(rr==0)?0:rr-1;
            for(k=0;k<4;k=k+1) begin
                dut.coord_x[k]=27'd100<<16;
                dut.coord_y[k]=(1079-rr)<<16;
            end
            ha=0;hb=1;
            if(which==1) begin
                // miss-b：A命中而B缺失，目标B=rr（rr最大1078）。
                ha=1;hb=0;
                dut.sim_a=rr+1;dut.sim_b=rr;
                for(k=0;k<4;k=k+1) dut.coord_y[k]=(1078-rr)<<16;
            end
            if(which==2) begin
                // 预取：当前两源行命中，下一输出行尚未加载。
                ha=1;hb=1;ph=0;dut.identity_mode=1;
                dut.consume_y=rr-1;dut.consume_x=16;
            end
            row_saved=rr;expected=sl*1048576+rr*960;
            #1;old_addr=addr;loads_saved=loads;
            // gnt预先高，地址准备时仍不能受理。
            gnt=1;
            @(posedge clk);#1;
            check(dut.state==4'd11,"C0 enters READ_ADDR");
            check(dut.load_row===row_saved,"C0 row selection");
            bank_saved=dut.load_bank;
            check(!bad_prepare(req,dut.cache_load_begin,loads_saved,loads),"C0 request/count must stay idle");
            if(FAULT!=0) begin
                force dut.o_corr_rd_req=1'b1;
                #1;
                check(!bad_prepare(req,dut.cache_load_begin,loads_saved,loads),"injected early request must FAIL");
                release dut.o_corr_rd_req;
            end
            check(addr===old_addr,"C0 address unchanged");
            if(which==2) check(dut.prefetch_active,"prefetch remains active");
            // 预取时扰动FIFO头，地址必须仍使用已锁存行。
            @(negedge clk);
            if(which==2) begin
                for(k=0;k<4;k=k+1) dut.coord_y[k]=(1079-700)<<16;
                dut.sample_phase=0;
                #1;
                check(dut.sample_dispatch,"READ_ADDR permits prefetch sampling");
                check(dut.map_issue==0,"gen_done prevents surplus mapping");
                dut.gen_done=0;#1;
                check(dut.map_issue,"READ_ADDR permits mapping when FIFO has space");
                dut.gen_done=1;
            end
            @(posedge clk);#1;
            check(dut.state==4'd5 && req,"C1 address and req issued together");
            check(addr===expected && len==119,"C1 exact slot/row address and length");
            check(loads==loads_saved,"gnt high before req is not a transfer");
            check(dut.load_row===row_saved && dut.load_bank==bank_saved,"latched row/bank stable");
        end
    endtask
    task accept_request;
        input integer stalls,boundary;
        begin
            @(negedge clk);gnt=0;
            repeat(stalls) begin
                @(posedge clk);#1;
                check(req && addr===expected && len==119,"request stable under grant stall");
                check(loads==loads_saved && !dut.cache_load_begin,"no grant no load");
                @(negedge clk);
            end
            if(boundary>=0) begin
                dut.consume_x=boundary;
                // 边界统计：当前行未加载，接受沿置位优先于同沿行末清除。
                dut.current_line_loaded=0;dut.sample_phase=0;
            end
            gnt=1;
            #1;check(dut.cache_load_begin,"grant acceptance drives load_begin");
            @(posedge clk);#1;
            accepted_tick=clock_ticks;
            check(dut.state==4'd6 && !req,"accepted request enters READ_WAIT");
            check(loads==loads_saved+1,"exactly one load counted");
            check(dut.u_cache.load_active && dut.u_cache.load_row===row_saved &&
                  dut.u_cache.load_bank==bank_saved,"cache consumer aligns with acceptance");
            check(dut.replace_cursor==((bank_saved==3)?0:bank_saved+1),"replacement advances on acceptance");
            check(dut.current_line_loaded,"line loaded flag set on acceptance");
            if(boundary==1919) check(hits==1,"line-end hit counted before accepted load sets next state");
        end
    endtask
    task malformed_return;
        input integer early;
        begin
            prepare(1,1,0);accept_request(1,-1);
            @(negedge clk);gnt=0;
            for(j=0;j<(early?1:120);j=j+1) begin
                vld=1;last=early;data=0;
                @(posedge clk);#1;
                if(early || j==119)
                    check(dut.load_error && !dut.load_done &&
                          !dut.u_cache.tag_valid[bank_saved],"bad last rejected and tag invalidated");
                @(negedge clk);
            end
            vld=0;last=0;
            check(dut.state==4'd6 && loads==loads_saved+1,"bad burst neither completes nor reissues");
            error_cases=error_cases+1;
            reset_dut;
        end
    endtask
    task return_line;
        input integer latency;
        begin
            // 从已受理沿到首数据恰为latency个周期；120拍连续有效。
            @(negedge clk);gnt=0;
            repeat(latency-1) @(negedge clk);
            for(j=0;j<120;j=j+1) begin
                vld=1;last=(j==119);data={8{32'h12340000+j}};
                @(posedge clk);#1;
                if(j==0) check(clock_ticks-accepted_tick==latency,"exact grant-to-first-data latency");
                check(!dut.load_error,"continuous return accepted without error");
                if(j<119) check(dut.state==4'd6,"one outstanding through last beat");
                @(negedge clk);
                if(gap_enable && j<119 && j%13==0) begin
                    vld=0;last=0;
                    @(negedge clk);
                end
            end
            vld=0;last=0;
            check(dut.u_cache.tag_valid[bank_saved] &&
                  dut.u_cache.tag_row[bank_saved]===row_saved,"line tag published at last beat");
            for(k=0;k<120;k=k+1) begin
                case(bank_saved)
                    0: check(dut.u_cache.BANK[0].ram[k]==={8{32'h12340000+k}},"bank0 full burst data");
                    1: check(dut.u_cache.BANK[1].ram[k]==={8{32'h12340000+k}},"bank1 full burst data");
                    2: check(dut.u_cache.BANK[2].ram[k]==={8{32'h12340000+k}},"bank2 full burst data");
                    3: check(dut.u_cache.BANK[3].ram[k]==={8{32'h12340000+k}},"bank3 full burst data");
                endcase
            end
            @(posedge clk);#1;
            check(dut.state==((MODE!=0)?4'd7:4'd4),"load completion returns to original state");
            check(loads==loads_saved+1,"no duplicate load counts");
            cases=cases+1;
        end
    endtask
    initial begin
        if(FAULT!=0) fd=$fopen("core_g4_fault_injection_result.txt","w");
        else if(MODE==0) fd=$fopen("core_g4_protocol_result.txt","w");
        else fd=$fopen("core_g4_protocol_sim_result.txt","w");
        force dut.hit_a=ha;force dut.hit_b=hb;force dut.prefetch_hit=ph;
        force dut.map_valid=1'b0;
        boundaries[0]=1918;boundaries[1]=1919;boundaries[2]=0;
        // 槽、首/末行、A/B缺失及三种首返回延迟的组合。
        for(slot_no=0;slot_no<4;slot_no=slot_no+1)
            for(row_no=0;row_no<3;row_no=row_no+1)
                for(kind=0;kind<2;kind=kind+1) begin
                    if(row_no==0) j=0;
                    else if(row_no==1) j=1;
                    else j=(kind==0)?1079:1078;
                    prepare(slot_no,j,kind);
                    accept_request((slot_no+row_no)%4,-1);
                    case(row_no)
                        0: return_line(1);
                        1: return_line(16);
                        2: return_line(64);
                    endcase
                end
        if(MODE==0) begin
            for(stall_no=0;stall_no<3;stall_no=stall_no+1) begin
                prepare(2,100,2);
                accept_request(3,boundaries[stall_no]);
                return_line(16);
            end
        end
        prepare(0,1,0);accept_request(2,-1);gap_enable=1;
        return_line(1);gap_enable=0;
        malformed_return(1);malformed_return(0);
        // 新状态、授权等待、返回等待期间复位；复位后重新走一笔有效事务。
        for(reset_phase=0;reset_phase<3;reset_phase=reset_phase+1) begin
            if(reset_phase==0) begin
                reset_dut;
                dut.state=4'd11;dut.load_row=1079;dut.source_slot=3;
            end else begin
                prepare(1,1,0);
                if(reset_phase==2) accept_request(2,-1);
            end
            reset_dut;
            check(dut.state==0 && dut.u_cache.tag_valid==0 && !rel,"reset removes pending transaction");
        end
        prepare(3,1079,0);accept_request(1,-1);return_line(64);
        // 检查器负向用例：提前req、提前begin、提前计数均必须判错。
        if(bad_prepare(1,0,0,0)) negatives=negatives+1;
        if(bad_prepare(0,1,0,0)) negatives=negatives+1;
        if(bad_prepare(0,0,0,1)) negatives=negatives+1;
        check(negatives==3 && !bad_prepare(0,0,0,0),"negative injection detects illegal combinations");
        if(err==0) begin
            $fdisplay(fd,"[G4 protocol] PASS mode=%0d transactions=%0d malformed=%0d negative_checks=%0d",MODE,cases,error_cases,negatives);
            $fdisplay(fd,"=== ALL TESTS PASSED (err=0) ===");
            $display("=== ALL TESTS PASSED (err=0) ===");
        end else $fdisplay(fd,"FAIL err=%0d",err);
        $fclose(fd);$finish;
    end
    initial begin
        #2000000;$fdisplay(fd,"FAIL TIMEOUT");$fclose(fd);$finish;
    end
endmodule
