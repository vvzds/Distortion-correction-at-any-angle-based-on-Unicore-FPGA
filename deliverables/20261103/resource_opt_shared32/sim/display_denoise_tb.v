`timescale 1ns/1ps
module display_denoise_tb;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0,de=0,hs=0,vs=0;
    reg [1:0] level=0;
    reg [15:0] rgb=0;
    wire [15:0] result;
    wire out_de,out_hs,out_vs;
    display_denoise dut(clk,rst_n,level,rgb,de,hs,vs,result,out_de,out_hs,out_vs);

    task send;
        input [15:0] pixel;
        input active;
        begin @(negedge clk);rgb=pixel;de=active;end
    endtask
    task check_pixel;
        input [15:0] expected;
        input [160*8-1:0] label_text;
        begin
            @(posedge clk);#1;
            if(result!==expected || !out_de)
                $fatal(1,"%0s: expected %h, got %h DE=%b",label_text,expected,result,out_de);
        end
    endtask
    initial begin
        repeat(4) @(negedge clk);rst_n=1;
        level=3;
        repeat(3) @(negedge clk);
        @(negedge clk);vs=1;
        @(negedge clk);vs=0;

        send(16'h8410,1);send(16'h8410,1);send(16'h8410,1);
        send(16'h8410,1);check_pixel(16'h8410,"flat area unchanged");

        send(16'h8410,1);send(16'h8410,1);send(16'hffff,1);
        send(16'h8410,1);send(16'h8410,1);
        check_pixel(16'h8410,"isolated impulse suppressed");

        send(16'h2104,1);send(16'h2104,1);send(16'h2104,1);
        send(16'hffff,1);send(16'hffff,1);
        check_pixel(16'h2104,"hard edge preserved");

        send(16'h0000,0);send(16'h0000,0);send(16'h0000,0);
        level=0;
        repeat(3) @(negedge clk);
        @(negedge clk);vs=1;
        @(negedge clk);vs=0;
        send(16'h4208,1);send(16'h8410,1);send(16'hc618,1);
        send(16'h6310,1);send(16'h0000,0);check_pixel(16'hc618,"disabled mode exact center passthrough");
        $display("PASS display_denoise flat, impulse, edge guard and disabled passthrough");
        $finish;
    end
    initial begin #100000;$fatal(1,"Timeout");end
endmodule
