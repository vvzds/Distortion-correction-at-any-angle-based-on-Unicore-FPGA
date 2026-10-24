`timescale 1ns/1ps
module calibration_map_tb;
    `include "parameters/calibration_q16.vh"
    reg clk=0; always #4 clk=~clk;
    reg rst_n=0,init=0,valid=0;
    reg [10:0] u=0,v=0;
    wire ready,out_valid;
    wire [26:0] sx,sy;
    reg [53:0] expected[0:2073599];
    integer n,count=0,err=0,slot,word_a,word_b,ra,rb,x;
    undistort_map dut(.clk(clk),.rst_n(rst_n),.i_frame_init(init),
        .i_fx(CAL_FX),.i_fy(CAL_FY),.i_cx(CAL_CX),.i_cy(CAL_CY),
        .i_k1(CAL_K1),.i_k2(CAL_K2),.i_p1(CAL_P1),.i_p2(CAL_P2),
        .i_aff_a11(32'sh10000),.i_aff_a12(32'sd0),.i_aff_a21(32'sd0),
        .i_aff_a22(32'sh10000),.i_aff_tx(32'sd0),.i_aff_ty(32'sd0),.i_aff_en(1'b0),
        .o_init_done(ready),.i_valid(valid),.i_u(u),.i_v(v),
        .o_valid(out_valid),.o_sx_q16(sx),.o_sy_q16(sy));
    always @(posedge clk) begin
        #1;
        if(out_valid) begin
            if(count>=2073600 || {sx,sy}!==expected[count]) begin
                if(err<8) $display("MAP_MISMATCH n=%0d got=%h exp=%h",count,{sx,sy},expected[count]);
                err=err+1;
            end
            if((^sx===1'bx)||(^sy===1'bx)||sx>1919*65536||sy>1079*65536) err=err+1;
            ra=1079-sy[26:16]; rb=(ra==0)?0:ra-1; x=sx[26:16];
            for(slot=0;slot<4;slot=slot+1) begin
                word_a=(slot<<20)+ra*960+(x>>1);
                word_b=(slot<<20)+rb*960+(x>>1);
                if(ra<0||ra>1079||rb<0||rb>1079||
                    word_a<(slot<<20)||word_b<(slot<<20)||
                    word_a>=(slot<<20)+1036800||word_b>=(slot<<20)+1036800) err=err+1;
            end
            count=count+1;
        end
    end
    initial begin
        $readmemh("vectors/map_expected.hex",expected);
        #30;rst_n=1;
        @(negedge clk);init=1;
        @(negedge clk);init=0;
        wait(ready);
        for(n=0;n<2073600;n=n+1) begin
            @(negedge clk); valid=1;u=n%1920;v=1079-n/1920;
        end
        @(negedge clk);valid=0;
        repeat(30) @(negedge clk);
        if(count!=2073600||err!=0) $fatal(1,"MAP FAIL count=%0d err=%0d",count,err);
        $display("MAP PASS pixels=%0d err=0 bit_exact_model=1 all_four_source_slots_checked=1",count);
        $finish;
    end
    initial begin #25000000;$fatal(1,"MAP TIMEOUT count=%0d",count);end
endmodule
