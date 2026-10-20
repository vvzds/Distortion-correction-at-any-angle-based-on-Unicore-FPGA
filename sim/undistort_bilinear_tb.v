`timescale 1ns/1ps
module undistort_bilinear_tb;
    reg clk = 0;
    reg rst_n = 0;
    reg i_valid = 0;
    reg [15:0] i_p00 = 0, i_p01 = 0, i_p10 = 0, i_p11 = 0;
    reg [11:0] i_wx = 0, i_wy = 0;
    wire o_valid;
    wire [15:0] o_pixel;
    integer err = 0;
    integer k;
    integer log_fd;
    reg [15:0] expected;

    undistort_bilinear dut (
        .clk(clk), .rst_n(rst_n), .i_valid(i_valid),
        .i_p00(i_p00), .i_p01(i_p01), .i_p10(i_p10), .i_p11(i_p11),
        .i_wx(i_wx), .i_wy(i_wy), .o_valid(o_valid), .o_pixel(o_pixel)
    );
    always #4 clk = ~clk;

    function [15:0] gold;
        input [15:0] a,b,c,d;
        input [11:0] x,y;
        real xf,yf,rr,gg,bb;
        reg [4:0] r5,b5;
        reg [5:0] g6;
        begin
            xf=x/4096.0; yf=y/4096.0;
            rr=(1-yf)*((1-xf)*a[15:11]+xf*b[15:11])
               +yf*((1-xf)*c[15:11]+xf*d[15:11]);
            gg=(1-yf)*((1-xf)*a[10:5]+xf*b[10:5])
               +yf*((1-xf)*c[10:5]+xf*d[10:5]);
            bb=(1-yf)*((1-xf)*a[4:0]+xf*b[4:0])
               +yf*((1-xf)*c[4:0]+xf*d[4:0]);
            r5=$rtoi(rr+0.5);
            g6=$rtoi(gg+0.5);
            b5=$rtoi(bb+0.5);
            gold={r5,g6,b5};
        end
    endfunction

    task check;
        input [15:0] a,b,c,d;
        input [11:0] x,y;
        begin
            @(negedge clk);
            i_p00=a; i_p01=b; i_p10=c; i_p11=d;
            i_wx=x; i_wy=y; i_valid=1;
            expected=gold(a,b,c,d,x,y);
            @(posedge clk); #1;
            @(posedge clk); #1;
            if (o_valid !== 1'b1 || o_pixel !== expected) begin
                $display("FAIL: x=%d y=%d got=%h expected=%h vld=%b",x,y,o_pixel,expected,o_valid);
                err=err+1;
            end
        end
    endtask

    initial begin
        #200000;
        $display("FAIL: watchdog timeout");
        $finish;
    end
    initial begin
        log_fd=$fopen("bilinear_result.txt","w");
        repeat(3) @(negedge clk);
        if (o_valid !== 0) err=err+1;
        rst_n=1;
        check(16'hA55A,16'h1234,16'hFEDC,16'h0000,0,0);
        check(16'h0000,16'hFFFF,16'hFFFF,16'h0000,12'd2048,12'd2048);
        check(16'hFFFF,16'hFFFF,16'hFFFF,16'hFFFF,12'd4095,12'd4095);
        for (k=0;k<1000;k=k+1)
            check($random,$random,$random,$random,$random,$random);
        @(negedge clk); i_valid=0;
        @(posedge clk); #1;
        @(posedge clk); #1;
        if (o_valid !== 0) err=err+1;
        if (err==0 && k==1000) begin
            $display("=== ALL TESTS PASSED (err=0) ===");
            $fdisplay(log_fd,"=== ALL TESTS PASSED (err=0) === random_cases=%0d",k);
        end else begin
            $display("=== TEST FAILED: err=%0d ===",err);
            $fdisplay(log_fd,"=== TEST FAILED: err=%0d random_cases=%0d ===",err,k);
        end
        $fclose(log_fd);
        $finish;
    end
endmodule
