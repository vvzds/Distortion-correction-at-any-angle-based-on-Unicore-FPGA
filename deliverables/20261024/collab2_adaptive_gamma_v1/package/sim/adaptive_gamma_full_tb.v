`timescale 1ns/1ps
module adaptive_gamma_full_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,en=1,v=0,sop=0,eop=0,sof=0,eof=0;
    reg [15:0] p=0;
    wire ov;wire [15:0] op;
    integer n,f,err=0,checks=0;
    reg [15:0] expected;
    adaptive_gamma dut(.clk(clk),.rst_n(rst_n),.i_enable(en),
        .i_pix_vld(v),.i_pix(p),.i_sop(sop),.i_eop(eop),
        .i_sof(sof),.i_eof(eof),.o_pix_vld(ov),.o_pix(op));
    // 完整1080p、无消隐相邻帧、白图累加上界、首末像素均计入。
    initial begin
        repeat(3) @(negedge clk);rst_n=1;
        for(f=0;f<3;f=f+1) begin
            for(n=0;n<2073600;n=n+1) begin
                @(negedge clk);
                v=1;p=(f==0)?16'hffff:16'h8410;
                sop=(n%1920==0);eop=(n%1920==1919);
                sof=(n==0);eof=(n==2073599);
                // 白帧平均255使下一帧从档2移至档3。
                expected=(f==0)?16'hffff:((f==1)?16'h736e:16'h8410);
                @(posedge clk);#1;
                if(!ov || op!==expected) begin
                    if(err<5) $display("FAIL full frame=%0d pixel=%0d got=%h expected=%h",f,n,op,expected);
                    err=err+1;
                end
                checks=checks+1;
            end
            if(f==0 && dut.sum!==29'd528768000) err=err+1;
        end
        @(negedge clk);v=0;
        @(posedge clk);#1;if(ov)err=err+1;
        $display("FULL_FRAME_PIXELS=%0d err=%0d",checks,err);
        if(err==0) $display("=== ALL TESTS PASSED (err=0) ===");
        else $display("FAIL err=%0d",err);
        $finish;
    end
endmodule
