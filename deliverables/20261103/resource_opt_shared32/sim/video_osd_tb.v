`timescale 1ns/1ps
module video_osd_tb;
    reg core_clk=0,pix_clk=0;
    always #4 core_clk=~core_clk;
    always #7 pix_clk=~pix_clk;
    reg core_rst_n=0,pix_rst_n=0,row_valid=0,enable=0,de=0,vs=0;
    reg [2:0] row_index=0;
    reg [383:0] row_data={48{8'h20}};
    reg [11:0] x=0,y=0;
    reg [23:0] rgb_in=24'h123456;
    wire [23:0] rgb_out;

    video_osd dut(
        .core_clk(core_clk),.core_rst_n(core_rst_n),.row_valid(row_valid),
        .enable(enable),.row_index(row_index),.row_data(row_data),
        .pix_clk(pix_clk),.pix_rst_n(pix_rst_n),.x(x),.y(y),
        .de(de),.vs(vs),.rgb_in(rgb_in),.rgb_out(rgb_out));

    initial begin
        repeat(5) @(negedge core_clk);
        core_rst_n=1;pix_rst_n=1;
        row_data[0+:8]=8'h41;
        @(negedge core_clk);row_valid=1;
        @(negedge core_clk);row_valid=0;
        repeat(8) @(negedge pix_clk);
        enable=1;
        repeat(5) @(negedge pix_clk);
        vs=1;
        @(negedge pix_clk);vs=0;
        x=34;y=32;de=1;#1;
        if(rgb_out!==24'h69e1d2) $fatal(1,"First character pixel missing");
        x=32;#1;
        if(rgb_out!==24'h11242c) $fatal(1,"Glyph background wrong");
        x=900;y=100;#1;
        if(rgb_out!==rgb_in) $fatal(1,"Pixels outside overlay changed");
        x=34;y=128;#1;
        if(rgb_out!==rgb_in) $fatal(1,"Removed rows still cover video");
        x=34;y=32;de=0;#1;
        if(rgb_out!==rgb_in) $fatal(1,"Blanking pixel changed");
        de=1;enable=0;
        repeat(4) @(negedge pix_clk);
        if(rgb_out!==24'h69e1d2) $fatal(1,"Visibility changed within frame");
        vs=1;@(negedge pix_clk);vs=0;#1;
        if(rgb_out!==rgb_in) $fatal(1,"Overlay hide failed");
        $display("PASS video_osd glyph, panel, passthrough, blanking, frame-boundary visibility");
        $finish;
    end
    initial begin #100000;$fatal(1,"OSD timeout");end
endmodule
