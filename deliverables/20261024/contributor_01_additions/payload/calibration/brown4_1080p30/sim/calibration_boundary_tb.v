`timescale 1ns/1ps
module calibration_boundary_tb;
    `include "parameters/calibration_q16.vh"
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,init=0,valid=0;
    reg [10:0] u=0,v=0;
    reg signed [31:0] tx=0,ty=0;
    wire ready,out_valid;wire [26:0] sx,sy;
    integer pass_checks=0,ex,ey,dx,dy,ra,rb,t;
    undistort_map dut(.clk(clk),.rst_n(rst_n),.i_frame_init(init),
        .i_fx(CAL_FX),.i_fy(CAL_FY),.i_cx(CAL_CX),.i_cy(CAL_CY),
        .i_k1(32'sd0),.i_k2(32'sd0),.i_p1(32'sd0),.i_p2(32'sd0),
        .i_aff_a11(32'sh10000),.i_aff_a12(32'sd0),.i_aff_a21(32'sd0),
        .i_aff_a22(32'sh10000),.i_aff_tx(tx),.i_aff_ty(ty),.i_aff_en(1'b1),
        .o_init_done(ready),.i_valid(valid),.i_u(u),.i_v(v),
        .o_valid(out_valid),.o_sx_q16(sx),.o_sy_q16(sy));
    task point;
        input integer px,py;
        begin
            ex=px*65536+tx;ey=py*65536+ty;
            if(ex<0)ex=0;if(ex>1919*65536)ex=1919*65536;
            if(ey<0)ey=0;if(ey>1079*65536)ey=1079*65536;
            @(negedge clk);valid=1;u=px;v=py;
            @(negedge clk);valid=0;
            wait(out_valid);#1;
            dx=$signed({1'b0,sx})-ex;dy=$signed({1'b0,sy})-ey;
            if((^sx===1'bx)||(^sy===1'bx)||dx>1310||dx< -1310||dy>1310||dy< -1310)
                $fatal(1,"Boundary map mismatch x=%0d y=%0d dx=%0d dy=%0d",px,py,dx,dy);
            if((ex==0&&sx!=0)||(ex==1919*65536&&sx!=1919*65536)||
                (ey==0&&sy!=0)||(ey==1079*65536&&sy!=1079*65536))$fatal(1,"Clamp endpoint mismatch");
            ra=1079-sy[26:16];rb=(ra==0)?0:ra-1;
            if(ra<0||ra>1079||rb<0||rb>1079)$fatal(1,"Boundary memory row wrap");
            pass_checks=pass_checks+1;
            @(negedge clk);
        end
    endtask
    initial begin
        #30;rst_n=1;
        for(t=0;t<4;t=t+1) begin
            case(t)
                0:begin tx=-40*65536-32768;ty=-40*65536-32768;end
                1:begin tx=40*65536+32768;ty=40*65536+32768;end
                2:begin tx=-4096*65536;ty=-4096*65536;end
                3:begin tx=4096*65536;ty=4096*65536;end
            endcase
            @(negedge clk);init=1;@(negedge clk);init=0;
            wait(ready);
            point(0,0);point(1919,0);point(0,1079);point(1919,1079);
            point(960,540);point(40,40);point(1879,1039);point(41,41);
        end
        $display("BOUNDARY PASS checks=%0d clamps_all_edges=1 rowB_zero=1",pass_checks);
        $finish;
    end
    initial begin #100000;$fatal(1,"Boundary TIMEOUT");end
endmodule
