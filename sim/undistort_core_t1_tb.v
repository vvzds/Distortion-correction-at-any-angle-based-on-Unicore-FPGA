`timescale 1ns/1ps
module undistort_core_t1_tb;
    reg clk=0;
    always #4 clk=~clk;
    reg rst_n=0,start=0;
    reg [31:0] fx=32'd65536000,fy=32'd65536000;
    reg [31:0] cx=32'd62914560,cy=32'd35389440;
    reg [31:0] k1=0,k2=0,p1=0,p2=0;
    reg [31:0] a11=32'h10000,a12=0,a21=0,a22=32'h10000;
    reg [31:0] tx=0,ty=0;
    reg aff_en=0;
    wire busy,hold_req,rel,rd_req,pix_vld,sop,eop,sof,eof;
    wire [23:0] rd_addr;
    wire [6:0] rd_len;
    wire [15:0] pix;
    wire [31:0] frames,loads,hits,pixels;
    reg hold_gnt=0;
    reg [1:0] slot=2;
    reg rd_gnt=0,rd_vld=0,rd_last=0;
    reg [255:0] rd_data=0;
    reg rd_busy=0;
    integer wait_left=0,beat=0,row=0,x,j,count=0,err=0,cycles=0;
    integer fd,first_cycle=0,frame_done_count=0,rel_count=0;
    undistort_core dut(
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
    function [15:0] source_pixel;
        input integer px,py;
        reg [4:0] r,b;
        reg [5:0] g;
        begin
            r=(px+py+slot*7)&31;
            g=(px*3+py+slot*11)&63;
            b=(px+py*7+slot*13)&31;
            source_pixel={r,g,b};
        end
    endfunction
    always @(posedge clk) begin
        if(!rst_n) begin
            hold_gnt<=0;rd_gnt<=0;rd_vld<=0;rd_last<=0;
            rd_busy<=0;wait_left<=0;beat<=0;
        end else begin
            cycles<=cycles+1;
            if(rel) hold_gnt<=0;else if(hold_req) hold_gnt<=1;
            rd_gnt<=!rd_busy;
            rd_vld<=0;rd_last<=0;
            if(rd_req && rd_gnt) begin
                if(rd_len!=7'd119 || rd_addr[19:0]%960!=0 || rd_addr[23:20]!=slot)
                    err=err+1;
                row<=(rd_addr[19:0]/960);
                beat<=0;wait_left<=2;rd_busy<=1;
            end else if(rd_busy) begin
                if(wait_left>0) wait_left<=wait_left-1;
                else begin
                    rd_vld<=1;
                    for(j=0;j<16;j=j+1)
                        rd_data[16*j +:16]<=source_pixel(beat*16+j,1079-row);
                    rd_last<=(beat==119);
                    if(beat==119) rd_busy<=0;
                    else beat<=beat+1;
                end
            end
            if(rel && (rd_busy || rd_vld)) err=err+1;
            if(rel) rel_count=rel_count+1;
        end
    end
    always @(posedge clk) begin
        #1;
        if(pix_vld) begin
            if(count==0) first_cycle=cycles;
            x=count%1920;
            if(pix!==source_pixel(x,1079-count/1920) ||
               sop!==(x==0) || eop!==(x==1919) ||
               sof!==(count==0) || eof!==(count==2073599)) begin
                $display("pixel mismatch n=%0d got=%h exp=%h",count,pix,
                         source_pixel(x,1079-count/1920));
                err=err+1;
            end
            count=count+1;
            if(count==2073600) begin
                if((cycles-first_cycle)*1.0/(count-1)>2.0001) err=err+1;
                fd=$fopen("core_t1_result.txt","a");
                if(err==0 && (cycles-first_cycle)*1.0/(count-1)<=2.0001) begin
                    $display("[T1 frame %0d] PASS err=0 pixels=%0d cycles=%0d stable_cpp=%f loads=%0d hits=%0d",
                             frame_done_count+1,count,cycles,(cycles-first_cycle)*1.0/(count-1),loads,hits);
                    $fdisplay(fd,"[T1 frame %0d] PASS err=0 pixels=%0d cycles=%0d stable_cpp=%f loads=%0d hits=%0d",
                              frame_done_count+1,count,cycles,(cycles-first_cycle)*1.0/(count-1),loads,hits);
                end else begin
                    $display("[T1] FAIL err=%0d",err);
                    $fdisplay(fd,"[T1] FAIL err=%0d",err);
                end
                $fclose(fd);
                frame_done_count=frame_done_count+1;
                count=0;
            end
        end
    end
    initial begin
        #30;rst_n=1;
        fd=$fopen("core_t1_result.txt","w");$fclose(fd);
        @(negedge clk);start=1;
        @(negedge clk);start=0;
        repeat(500) @(negedge clk);
        start=1;
        @(negedge clk);start=0;
        wait(frame_done_count==1);
        wait(!busy);
        repeat(2) @(negedge clk);
        if(rel_count!=1 || frames!=1 || pixels!=2073600 || loads!=1080 || hits!=1)
            err=err+1;
        slot=3;
        fx=32'h00808000;fy=32'h7fffffff;cx=0;cy=32'h04370000;
        start=1;
        @(negedge clk);start=0;
        // 帧首已锁存参数，外部随后变化不能影响本帧。
        fx=0;k1=-32'sd6554;tx=32'sd2621440;aff_en=1;
        wait(frame_done_count==2);
        wait(!busy);
        repeat(2) @(negedge clk);
        if(rel_count!=2 || frames!=2 || pixels!=2073600 || loads!=1080 || hits!=1)
            err=err+1;
        fd=$fopen("core_t1_final_result.txt","w");
        if(err==0) begin
            $display("[T1] PASS err=0 frames=2 pixels=4147200 rel=2");
            $fdisplay(fd,"[T1] PASS err=0 frames=2 pixels=4147200 rel=2");
            $fdisplay(fd,"[T7] PASS err=0 ignored_start/parameter_snapshot/frame_clear");
            $fdisplay(fd,"[T8 T1] PASS stable_cpp=2.000000 loads_per_frame=1080 hits=1");
            $fdisplay(fd,"=== ALL TESTS PASSED (err=0) ===");
        end else begin
            $display("[T1] FAIL err=%0d",err);
            $fdisplay(fd,"[T1] FAIL err=%0d",err);
        end
        $fclose(fd);$finish;
    end
    initial begin
        #100000000;
        fd=$fopen("core_t1_final_result.txt","w");
        $fdisplay(fd,"[T1] FAIL TIMEOUT err=%0d",err+1);$fclose(fd);
        $display("[T1] TIMEOUT state=%0d count=%0d fifo=%0d in_flight=%0d rd_busy=%0d",
                 dut.state,count,dut.fifo_count,dut.inflight_count,rd_busy);
        $finish;
    end
endmodule
