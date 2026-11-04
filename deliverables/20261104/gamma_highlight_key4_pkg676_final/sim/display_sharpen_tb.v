`timescale 1ns/1ps
module display_sharpen_tb;
    reg clk=0;
    always #7 clk=~clk;
    reg rst_n=0,de=0,hs=0,vs=0;
    reg [1:0] level=0;
    reg [15:0] rgb=0;
    wire [15:0] result;
    wire out_de,out_hs,out_vs;
    display_sharpen dut(clk,rst_n,level,rgb,de,hs,vs,result,out_de,out_hs,out_vs);
    task send;
        input [15:0] pixel;
        input active;
        begin @(negedge clk);rgb=pixel;de=active;end
    endtask
    initial begin
        repeat(4) @(negedge clk);rst_n=1;
        level=2;
        repeat(3) @(negedge clk);
        @(negedge clk);vs=1;
        @(negedge clk);vs=0;
        send(16'h8410,1);
        send(16'h8410,1);
        send(16'h8410,1);
        @(posedge clk);#1;if(!out_de || result!==16'h8410) $fatal(1,"Flat pixel changed");
        send(16'h0000,1);
        send(16'hffff,1);
        send(16'hffff,1);
        @(posedge clk);#1;if(result!==16'h0000) $fatal(1,"Black hard edge changed");
        send(16'hffff,1);
        @(posedge clk);#1;if(result!==16'hffff) $fatal(1,"Hard edge halo");
        send(16'h8410,0);
        @(posedge clk);#1;if(!out_de || result!==16'hffff) $fatal(1,"Penultimate pixel missing");
        send(16'h0000,0);
        @(posedge clk);#1;if(!out_de || result!==16'hffff) $fatal(1,"Last pixel missing");
        send(16'h0000,0);
        @(posedge clk);#1;if(out_de) $fatal(1,"DE remains active");
        send(16'h7bef,1);
        send(16'h8410,1);
        send(16'h9492,1);
        send(16'h8410,1);
        send(16'h7bef,1);
        @(posedge clk);#1;if(result!==16'h9cd3 || !out_de)
            $fatal(1,"Soft edge was not enhanced: %h",result);
        send(16'h0000,0);
        send(16'h0000,0);
        send(16'h0000,0);
        level=0;
        repeat(3) @(negedge clk);
        @(negedge clk);vs=1;
        @(negedge clk);vs=0;
        send(16'h4208,1);
        send(16'h8410,1);
        send(16'hc618,1);
        @(posedge clk);#1;if(result!==16'h4208) $fatal(1,"Off mode is not exact passthrough");
        send(16'h6310,1);
        @(posedge clk);#1;if(result!==16'h8410) $fatal(1,"Off mode middle pixel");
        send(16'h0000,0);
        @(posedge clk);#1;if(result!==16'hc618 || !out_de) $fatal(1,"Off mode second-last");
        send(16'h0000,0);
        @(posedge clk);#1;if(result!==16'h6310 || !out_de) $fatal(1,"Off mode right border");
        $display("PASS display_sharpen flat, black guard, hard edge, off passthrough and DE");
        $finish;
    end
    initial begin #100000;$fatal(1,"Timeout");end
endmodule
