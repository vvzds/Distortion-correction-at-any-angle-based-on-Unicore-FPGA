`timescale 1ns/1ps
module undistort_core_sim_tb;
    reg clk=0;
    always #4 clk=~clk;
    reg rst_n=0,start=0;
    reg signed [31:0] fx=32'd65536000,fy=32'd65536000;
    reg signed [31:0] cx=32'd62914560,cy=32'd35389440;
    reg signed [31:0] k1=0,k2=0,p1=0,p2=0;
    reg signed [31:0] a11=32'h10000,a12=0,a21=0,a22=32'h10000;
    reg signed [31:0] tx=0,ty=0;
    reg aff_en=0;
    wire busy,hold_req,rel,rd_req,pix_vld,sop,eop,sof,eof;
    wire [23:0] rd_addr;
    wire [6:0] rd_len;
    wire [15:0] pix;
    wire [31:0] frames,loads,hits,pixels;
    reg hold_gnt=0;
    reg [1:0] slot=0,latest_slot=1;
    reg held=0;
    integer grant_wait=0,grant_target=16;
    reg rd_gnt=0,rd_vld=0,rd_last=0;
    reg [255:0] rd_data=0;
    reg rd_busy=0,gap=0;
    integer wait_left=0,beat=0,row=0,err=0,cycles=0;
    integer fd,case_no,accepted=0,rel_count=0,accept_cycle=0,delay_target=1;
    reg first_pending=0,previous_rel=0;
    undistort_core #(.SIM_MODE(1)) dut(
        .clk(clk),.rst_n(rst_n),.i_fx(fx),.i_fy(fy),.i_cx(cx),.i_cy(cy),
        .i_k1(k1),.i_k2(k2),.i_p1(p1),.i_p2(p2),
        .i_aff_a11(a11),.i_aff_a12(a12),.i_aff_a21(a21),.i_aff_a22(a22),
        .i_aff_tx(tx),.i_aff_ty(ty),.i_aff_en(aff_en),
        .i_frame_start(start),.o_frame_busy(busy),
        .o_corr_src_hold_req(hold_req),.i_corr_src_hold_gnt(hold_gnt),
        .i_corr_src_slot(slot),.o_corr_src_rel(rel),
        .o_corr_rd_addr(rd_addr),.o_corr_rd_len(rd_len),.o_corr_rd_req(rd_req),
        .i_corr_rd_gnt(rd_gnt),.i_corr_rd_vld(rd_vld),
        .i_corr_rd_data(rd_data),.i_corr_rd_last(rd_last),
        .o_pix_vld(pix_vld),.o_pix(pix),.o_sop(sop),.o_eop(eop),
        .o_sof(sof),.o_eof(eof),.o_stat_frame_cnt(frames),
        .o_stat_line_loads(loads),.o_stat_line_hits(hits),.o_stat_pix_cnt(pixels)
    );
    always @(posedge clk) begin
        if(!rst_n) begin
            hold_gnt<=0;held<=0;grant_wait<=0;
            rd_gnt<=0;rd_vld<=0;rd_last<=0;
            rd_busy<=0;gap<=0;wait_left<=0;beat<=0;
        end else begin
            cycles<=cycles+1;
            if(rel) begin
                hold_gnt<=0;held<=0;grant_wait<=0;
                rel_count=rel_count+1;
                if(previous_rel || rd_busy || rd_vld || !busy) err=err+1;
            end else if(!held && hold_req) begin
                if(grant_wait>=grant_target) begin
                    held<=1;hold_gnt<=1;slot<=latest_slot;
                end else grant_wait<=grant_wait+1;
            end
            rd_gnt<=!rd_busy;
            rd_vld<=0;rd_last<=0;
            if(rd_req && rd_gnt) begin
                if(!held || rd_busy || rd_len!=119 ||
                   rd_addr[23:20]!=slot || rd_addr[19:0]>1036799 ||
                   rd_addr[19:0]%960!=0) begin
                    if(err<10) $display("DDR protocol violation addr=%h len=%0d",rd_addr,rd_len);
                    err=err+1;
                end
                row<=rd_addr[19:0]/960;
                accepted=accepted+1;accept_cycle=cycles;first_pending=1;
                delay_target=(case_no==1)?1:((case_no==2)?16:64);
                beat<=0;wait_left<=delay_target-1;
                rd_busy<=1;gap<=0;
                if(delay_target==1) begin rd_vld<=1;rd_data<=0;beat<=1;end
            end else if(rd_busy) begin
                if(wait_left>1) wait_left<=wait_left-1;
                else if(case_no==3 && beat%7==3 && !gap) gap<=1;
                else begin
                    gap<=0;rd_vld<=1;rd_data<=0;
                    rd_last<=(beat==119);
                    if(beat==119) rd_busy<=0;
                    else beat<=beat+1;
                end
            end
            if(first_pending && rd_vld) begin
                if(cycles-accept_cycle!=delay_target) err=err+1;
                first_pending=0;
            end
            previous_rel<=rel;
        end
    end
    always @(posedge clk) begin
        #1;
        if(!rst_n && (busy || hold_req || rd_req || pix_vld)) err=err+1;
        if(pix_vld || sop || eop || sof || eof) err=err+1;
        if(busy && held && dut.state!=dut.HOLD && hold_req) err=err+1;
    end
    task run_case;
        input integer n;
        begin
            case_no=n;
            accepted=0;
            grant_target=(n==1)?16:((n==2)?0:5);
            latest_slot=(n==1)?1:((n==2)?2:0);
            @(negedge clk);start=1;
            @(negedge clk);start=0;
            wait(busy);
            if(n==1) begin
                repeat(6) @(negedge clk);
                latest_slot=3;
            end
            wait(held);
            if(n==1 && slot!=3) err=err+1;
            repeat(20) @(negedge clk);
            start=1;
            @(negedge clk);start=0;
            wait(!busy);
            #1;
            repeat(3) @(negedge clk);
            if(loads!=1080 || hits!=0 || accepted!=loads || rel_count!=n ||
               pixels!=0 || frames!=n || hold_req || rd_req || rd_busy || held)
                err=err+1;
            $display("[T9 frame %0d] loads=%0d hits=%0d pixels=%0d frames=%0d err=%0d",
                     n,loads,hits,pixels,frames,err);
            $fdisplay(fd,"[T9 frame %0d] loads=%0d hits=%0d pixels=%0d frames=%0d err=%0d latency=%0d rel=%0d",
                      n,loads,hits,pixels,frames,err,delay_target,rel_count);
        end
    endtask
    initial begin
        fd=$fopen("core_sim_result.txt","w");
        #30;rst_n=1;
        @(negedge clk);fx=0;start=1;
        @(negedge clk);start=0;
        repeat(4) @(negedge clk);
        if(busy || hold_req || frames!=0) err=err+1;
        $display("[T0] %0s err=%0d",err==0?"PASS":"FAIL",err);
        fx=32'd65536000;
        run_case(1);run_case(2);run_case(3);
        if(err==0) begin
            $display("[T7] PASS err=0");
            $display("[T9] PASS err=0");
            $display("=== ALL TESTS PASSED (err=0) ===");
            $fdisplay(fd,"[T0] PASS err=0");
            $fdisplay(fd,"[T7] PASS err=0");
            $fdisplay(fd,"[T9] PASS err=0 frames=3");
            $fdisplay(fd,"=== ALL TESTS PASSED (err=0) ===");
        end else begin
            $display("[T7/T9] FAIL err=%0d",err);
            $fdisplay(fd,"[T7/T9] FAIL err=%0d",err);
        end
        $fclose(fd);$finish;
    end
    initial begin
        #150000000;
        $fdisplay(fd,"[T9] FAIL TIMEOUT err=%0d",err+1);
        $fclose(fd);
        $display("[T9] TIMEOUT state=%0d frames=%0d loads=%0d err=%0d",
                 dut.state,frames,loads,err);
        $finish;
    end
endmodule
