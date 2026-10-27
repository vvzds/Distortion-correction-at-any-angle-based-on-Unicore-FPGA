`timescale 1ns/1ps
module map_trace_tb;
    reg clk=0,rst_n=0,frame_init=0,in_valid=0;
    reg [10:0] u=0,v=0;
    reg signed [31:0] fx=32'sd98809312,fy=32'sd98789197;
    reg signed [31:0] cx=32'sd57903224,cy=32'sd37269520;
    reg signed [31:0] k1=-32'sd25001,k2=32'sd10269;
    reg signed [31:0] p1=-32'sd20,p2=-32'sd7;
    reg signed [31:0] a11=32'sd63303,a12=-32'sd16962;
    reg signed [31:0] a21=32'sd16962,a22=32'sd63303;
    reg signed [31:0] tx=32'sd11293562,ty=-32'sd15070336;
    wire init_done,out_valid;
    wire [26:0] sx,sy;
    wire [10:0] row_a=11'd1079-sy[26:16];
    wire [10:0] row_b=(sy[26:16]==11'd1079)?11'd0:11'd1078-sy[26:16];
    wire [4:0] seg0={1'b0,sx[26:23]};
    wire [10:0] next_x=(sx[26:16]==11'd1919)?11'd1919:sx[26:16]+11'd1;
    wire [4:0] seg1=next_x[10:7];
    wire [31:0] key={row_a,row_b,seg0,seg1};
    integer fd,n,produced=0;
    always #4 clk=~clk;

    undistort_map dut(
        .clk(clk),.rst_n(rst_n),.i_frame_init(frame_init),
        .i_fx(fx),.i_fy(fy),.i_cx(cx),.i_cy(cy),
        .i_k1(k1),.i_k2(k2),.i_p1(p1),.i_p2(p2),
        .i_aff_a11(a11),.i_aff_a12(a12),.i_aff_a21(a21),.i_aff_a22(a22),
        .i_aff_tx(tx),.i_aff_ty(ty),.i_aff_en(1'b1),
        .o_init_done(init_done),.i_valid(in_valid),.i_u(u),.i_v(v),
        .o_valid(out_valid),.o_sx_q16(sx),.o_sy_q16(sy)
    );

    always @(posedge clk) if(out_valid) begin
        $fdisplay(fd,"%08x",key);
        produced=produced+1;
    end

    initial begin
        fd=$fopen("map_keys.hex","w");
        #40 rst_n=1;
        @(negedge clk) frame_init=1;
        @(negedge clk) frame_init=0;
        wait(init_done);
        for(n=0;n<2073600;n=n+1)begin
            @(negedge clk);
            in_valid=1;
            u=n%1920;
            v=1079-n/1920;
        end
        @(negedge clk) in_valid=0;
        wait(produced==2073600);
        $fclose(fd);
        $display("TRACE PASS pixels=%0d",produced);
        $finish;
    end
    initial begin
        #50000000;
        $display("TRACE FAIL timeout pixels=%0d",produced);
        $finish;
    end
endmodule
