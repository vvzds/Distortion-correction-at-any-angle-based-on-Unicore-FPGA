`timescale 1ns/1ps
module adaptive_gamma_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_begin=0,frame_end=0,enable=1,in_valid=0,in_inside=1;
    reg [15:0] in_pixel=0;
    wire out_valid;wire [15:0] out_pixel;wire [1:0] mode;
    adaptive_gamma dut(clk,rst_n,frame_begin,frame_end,enable,in_valid,in_inside,
                       in_pixel,out_valid,out_pixel,mode);
    task begin_frame;
        input [1:0] expected;
        begin
            @(negedge clk);frame_begin=1;
            @(negedge clk);frame_begin=0;
            if(mode!==expected) $fatal(1,"Mode %0d expected %0d",mode,expected);
        end
    endtask
    task samples;
        input [15:0] pixel;input inside_image;
        integer n;
        begin
            @(negedge clk);in_pixel=pixel;in_inside=inside_image;in_valid=1;
            for(n=0;n<113;n=n+1) begin
                @(negedge clk);
                if(!out_valid) $fatal(1,"Lost pixel");
                if(mode==0 && out_pixel!==pixel) $fatal(1,"Linear changed pixel");
                if(mode==1 && pixel==16'h4208 && out_pixel!==16'h738e)
                    $fatal(1,"Bright LUT %h expected 738e",out_pixel);
                if(mode==2 && pixel==16'hc618 && out_pixel!==16'had35)
                    $fatal(1,"Dark LUT %h expected ad35",out_pixel);
            end
            in_valid=0;
            @(negedge clk);
            if(out_valid) $fatal(1,"Extra output");
        end
    endtask
    task end_frame;
        begin
            @(negedge clk);frame_end=1;
            @(negedge clk);frame_end=0;
            repeat(2) @(negedge clk);
        end
    endtask
    initial begin
        repeat(4) @(negedge clk);rst_n=1;
        begin_frame(0);samples(16'h4208,1);end_frame(); // mean64 -> brighten
        begin_frame(1);samples(16'h4208,1);samples(16'h0000,0);end_frame();
        begin_frame(1);samples(16'h528a,1);end_frame(); // mean80 hysteresis
        begin_frame(1);samples(16'h630c,1);end_frame(); // mean96 -> linear
        begin_frame(0);samples(16'hc618,1);end_frame(); // mean192 -> darken
        begin_frame(2);samples(16'hc618,1);end_frame();
        begin_frame(2);samples(16'hb596,1);end_frame(); // mean176 hysteresis
        begin_frame(2);samples(16'ha514,1);end_frame(); // mean160 -> linear
        begin_frame(0);samples(16'h0000,0);end_frame(); // invalid fill excluded
        begin_frame(0);samples(16'h0000,1);end_frame();
        enable=0;begin_frame(0);samples(16'h4208,1);end_frame();
        enable=1;begin_frame(1);
        enable=0;repeat(5) @(negedge clk);
        if(mode!=1) $fatal(1,"Mode changed within frame");
        end_frame();
        $display("PASS gamma transitions, hysteresis, invalid exclusion, disable and LUT values");$finish;
    end
    initial begin #1000000;$fatal(1,"Timeout");end
endmodule

