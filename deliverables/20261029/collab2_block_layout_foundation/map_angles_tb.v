`timescale 1ns/1ps
module map_angles_tb;
    reg clk=0,rst_n=0,frame_init=0,in_valid=0;
    reg [10:0] u=0,v=0;
    reg signed [31:0] fx=32'sd98809312,fy=32'sd98789197;
    reg signed [31:0] cx=32'sd57903224,cy=32'sd37269520;
    reg signed [31:0] k1=-32'sd25001,k2=32'sd10269;
    reg signed [31:0] p1=-32'sd20,p2=-32'sd7;
    reg signed [31:0] a11=32'sd65536,a12=0,a21=0,a22=32'sd65536;
    reg signed [31:0] tx=0,ty=0;
    wire init_done,out_valid;
    wire [26:0] sx,sy;
    integer fd,n,produced=0,angle=0;
    reg [255:0] trace_name;
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
    always @(posedge clk) if(out_valid)begin
        $fdisplay(fd,"%06x",{2'b0,sy[26:16],sx[26:16]});
        produced=produced+1;
    end
    initial begin
        if(!$value$plusargs("ANGLE=%d",angle))$fatal;
        if(!$value$plusargs("TRACE=%s",trace_name))$fatal;
        case(angle)
             0:begin a11=65536;a12=0;a21=0;a22=65536;tx=0;ty=0;end
            15:begin a11=63303;a12=-16962;a21=16962;a22=63303;tx=11293625;ty=-15070256;end
            30:begin a11=56756;a12=-32768;a21=32768;a22=56756;tx=26102899;ty=-26704000;end
            45:begin a11=46341;a12=-46341;a21=46341;a22=46341;tx=43418593;ty=-34108412;end
            60:begin a11=32768;a12=-56756;a21=56756;a22=32768;tx=62060672;ty=-36778893;end
            75:begin a11=16962;a12=-63303;a21=63303;a22=16962;tx=80758709;ty=-34533455;end
            90:begin a11=0;a12=-65536;a21=65536;a22=0;tx=98238464;ty=-27525120;end
            default:$fatal;
        endcase
        fd=$fopen(trace_name,"w");if(!fd)$fatal;
        #40 rst_n=1;
        @(negedge clk)frame_init=1;
        @(negedge clk)frame_init=0;
        wait(init_done);
        for(n=0;n<2073600;n=n+1)begin
            @(negedge clk);in_valid=1;u=n%1920;v=1079-n/1920;
        end
        @(negedge clk)in_valid=0;
        wait(produced==2073600);
        $fclose(fd);
        $display("TRACE PASS angle=%0d pixels=%0d",angle,produced);
        $finish;
    end
    initial begin
        #50000000;$display("TRACE FAIL timeout pixels=%0d",produced);$fatal;
    end
endmodule
