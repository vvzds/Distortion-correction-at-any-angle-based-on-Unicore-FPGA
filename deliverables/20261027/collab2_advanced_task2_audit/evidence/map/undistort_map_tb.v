`timescale 1ns/1ps
module undistort_map_tb;
    reg clk=0,rst_n=0,i_frame_init=0,i_valid=0,i_aff_en=0;
    reg signed [31:0] i_fx=0,i_fy=0,i_cx=0,i_cy=0;
    reg signed [31:0] i_k1=0,i_k2=0,i_p1=0,i_p2=0;
    reg signed [31:0] i_aff_a11=0,i_aff_a12=0,i_aff_a21=0,i_aff_a22=0;
    reg signed [31:0] i_aff_tx=0,i_aff_ty=0;
    reg [10:0] i_u=0,i_v=0;
    wire o_init_done,o_valid;
    wire [26:0] o_sx_q16,o_sy_q16;
    integer err=0,checks=0,fd,trace_fd,n,timer;
    integer burst_seen=0,burst_first_cycle=0,burst_last_cycle=0,cycles=0;
    real fxr,fyr,cxr,cyr,k1r,k2r,p1r,p2r;
    real a11r,a12r,a21r,a22r,txr,tyr;
    real xp,yp,xn,yn,r2,rad,xd,yd,sx,sy,gotx,goty;

    undistort_map dut(
        .clk(clk),.rst_n(rst_n),.i_frame_init(i_frame_init),
        .i_fx(i_fx),.i_fy(i_fy),.i_cx(i_cx),.i_cy(i_cy),
        .i_k1(i_k1),.i_k2(i_k2),.i_p1(i_p1),.i_p2(i_p2),
        .i_aff_a11(i_aff_a11),.i_aff_a12(i_aff_a12),
        .i_aff_a21(i_aff_a21),.i_aff_a22(i_aff_a22),
        .i_aff_tx(i_aff_tx),.i_aff_ty(i_aff_ty),.i_aff_en(i_aff_en),
        .o_init_done(o_init_done),.i_valid(i_valid),.i_u(i_u),.i_v(i_v),
        .o_valid(o_valid),.o_sx_q16(o_sx_q16),.o_sy_q16(o_sy_q16)
    );
    always #4 clk=~clk;
    always @(posedge clk) if(rst_n) cycles<=cycles+1;

    function signed [31:0] q;
        input real x;
        begin q=$rtoi(x*65536.0); end
    endfunction
    function real absval;
        input real x;
        begin absval=(x<0)?-x:x; end
    endfunction
    task start_frame;
        begin
            @(negedge clk); i_frame_init=1;
            @(negedge clk); i_frame_init=0;
            timer=0;
            while(o_init_done !== 1 && timer<120) begin
                @(posedge clk); #1; timer=timer+1;
            end
            if(o_init_done !== 1) begin
                $display("FAIL: reciprocal initialization timeout"); err=err+1;
            end
        end
    endtask
    task golden;
        input integer u,v;
        begin
            fxr=i_fx/65536.0;fyr=i_fy/65536.0;
            cxr=i_cx/65536.0;cyr=i_cy/65536.0;
            k1r=i_k1/65536.0;k2r=i_k2/65536.0;
            p1r=i_p1/65536.0;p2r=i_p2/65536.0;
            a11r=i_aff_a11/65536.0;a12r=i_aff_a12/65536.0;
            a21r=i_aff_a21/65536.0;a22r=i_aff_a22/65536.0;
            txr=i_aff_tx/65536.0;tyr=i_aff_ty/65536.0;
            xp=i_aff_en ? a11r*u+a12r*v+txr : u;
            yp=i_aff_en ? a21r*u+a22r*v+tyr : v;
            xn=(xp-cxr)/fxr;yn=(yp-cyr)/fyr;
            r2=xn*xn+yn*yn;
            rad=1.0+k1r*r2+k2r*r2*r2;
            xd=xn*rad+2.0*p1r*xn*yn+p2r*(r2+2.0*xn*xn);
            yd=yn*rad+p1r*(r2+2.0*yn*yn)+2.0*p2r*xn*yn;
            sx=fxr*xd+cxr;sy=fyr*yd+cyr;
            if(sx<0.0) sx=0.0; else if(sx>1919.0) sx=1919.0;
            if(sy<0.0) sy=0.0; else if(sy>1079.0) sy=1079.0;
        end
    endtask
    task sample_check;
        input integer u,v,identity;
        begin
            golden(u,v);
            @(negedge clk); i_u=u;i_v=v;i_valid=1;
            @(negedge clk); i_valid=0;
            timer=0;
            while(o_valid !== 1 && timer<40) begin
                @(posedge clk); #1; timer=timer+1;
            end
            gotx=o_sx_q16/65536.0;
            goty=o_sy_q16/65536.0;
            $fdisplay(trace_fd,"S %0d %0d %h %h",u,v,o_sx_q16,o_sy_q16);
            if(o_valid !== 1 ||
               (identity && (o_sx_q16 !== (u<<16) || o_sy_q16 !== (v<<16))) ||
               (!identity && (absval(gotx-sx)>0.02 || absval(goty-sy)>0.02))) begin
                $display("FAIL: map u=%0d v=%0d got=(%f,%f) exp=(%f,%f)",u,v,gotx,goty,sx,sy);
                $fdisplay(fd,"FAIL: map u=%0d v=%0d got=(%f,%f) exp=(%f,%f)",u,v,gotx,goty,sx,sy);
                err=err+1;
            end
            checks=checks+1;
        end
    endtask
    task burst_check;
        integer drive_n,see_n;
        begin
            i_fx=32'sd98809312;i_fy=32'sd98789197;
            i_cx=32'sd57903224;i_cy=32'sd37269520;
            i_k1=-32'sd25001;i_k2=32'sd10269;
            i_p1=-32'sd20;i_p2=-32'sd7;
            i_aff_a11=32'sd65287;i_aff_a12=-32'sd5712;
            i_aff_a21=32'sd5712;i_aff_a22=32'sd65287;
            i_aff_tx=32'sd3320540;i_aff_ty=-32'sd5346328;
            i_aff_en=1;
            start_frame();
            fork
                begin
                    for(drive_n=0;drive_n<8192;drive_n=drive_n+1) begin
                        @(negedge clk);
                        i_valid=1;
                        i_u=(drive_n*73)%1920;
                        i_v=(drive_n*191)%1080;
                    end
                    @(negedge clk);i_valid=0;
                end
                begin
                    wait(o_valid===1);
                    for(see_n=0;see_n<8192;see_n=see_n+1) begin
                        if(see_n!=0) begin @(posedge clk); #1; end
                        if(see_n==0) burst_first_cycle=cycles;
                        if(see_n==8191) burst_last_cycle=cycles;
                        golden((see_n*73)%1920,(see_n*191)%1080);
                        gotx=o_sx_q16/65536.0;
                        goty=o_sy_q16/65536.0;
                        $fdisplay(trace_fd,"B %0d %h %h",see_n,o_sx_q16,o_sy_q16);
                        if(o_valid!==1 || absval(gotx-sx)>0.02 || absval(goty-sy)>0.02) begin
                            if(err<12) $display("BURST FAIL n=%0d valid=%b got=(%f,%f) exp=(%f,%f)",see_n,o_valid,gotx,goty,sx,sy);
                            err=err+1;
                        end
                        burst_seen=burst_seen+1;
                    end
                end
            join
            @(posedge clk); #1;
            if(o_valid!==0 || burst_last_cycle-burst_first_cycle!=8191) err=err+1;
            $display("BURST accepted=%0d outputs=%0d output_span_cycles=%0d err=%0d",
                     8192,burst_seen,burst_last_cycle-burst_first_cycle,err);
            $fdisplay(fd,"BURST accepted=%0d outputs=%0d output_span_cycles=%0d err=%0d",
                      8192,burst_seen,burst_last_cycle-burst_first_cycle,err);
        end
    endtask
    initial begin
        #1000000;
        $display("FAIL: watchdog timeout");
        $finish;
    end
    initial begin
        fd=$fopen("map_result.txt","w");
        trace_fd=$fopen("map_trace.txt","w");
        repeat(4) @(negedge clk);rst_n=1;
        i_fx=q(1000.0);i_fy=q(1000.0);i_cx=q(960.0);i_cy=q(540.0);
        i_aff_a11=q(1.0);i_aff_a22=q(1.0);
        start_frame();
        sample_check(0,0,1);sample_check(960,540,1);
        sample_check(1919,1079,1);
        i_aff_en=1;start_frame();
        sample_check(1,2,1);sample_check(1919,1079,1);
        i_aff_en=0;i_k1=q(-0.1);start_frame();
        sample_check(0,200,0);sample_check(960,200,0);
        sample_check(1919,800,0);sample_check(1200,500,0);
        for(n=0;n<128;n=n+1) sample_check((n*73)%1920,(n*191)%1080,0);
        i_k1=q(0.05);i_p1=q(0.002);i_p2=q(-0.001);start_frame();
        for(n=0;n<30;n=n+1) sample_check((n*347)%1920,(n*179)%1080,0);
        i_k1=0;i_p1=0;i_p2=0;i_aff_en=1;
        i_aff_tx=q(40.5);start_frame();
        sample_check(100,500,0);sample_check(1919,500,0);
        i_aff_tx=q(-40.0);start_frame();
        sample_check(0,500,0);sample_check(1000,500,0);
        i_fx=q(128.0);i_fy=q(128.0);i_cx=0;i_cy=0;
        i_k1=q(-0.5);i_k2=q(0.5);i_p1=q(0.01);i_p2=q(-0.01);
        i_aff_tx=q(4096.0);i_aff_ty=q(-4096.0);start_frame();
        sample_check(0,0,0);sample_check(1919,1079,0);
        sample_check(960,540,0);
        i_aff_tx=q(-4096.0);i_aff_ty=q(4096.0);start_frame();
        sample_check(0,1079,0);sample_check(1919,0,0);
        // 合法极值交叉组合：不能以最终坐标钳位代替中间量溢出检查。
        i_fx=q(128.0);i_fy=q(128.0);i_cx=0;i_cy=0;
        i_p1=0;i_p2=0;i_k1=0;i_aff_en=1;
        for(n=0;n<64;n=n+1) begin
            i_aff_a11=(n&1)?q(2.0):q(-2.0);
            i_aff_a12=(n&2)?q(2.0):q(-2.0);
            i_aff_a21=(n&4)?q(2.0):q(-2.0);
            i_aff_a22=(n&8)?q(2.0):q(-2.0);
            i_aff_tx=(n&16)?q(4096.0):q(-4096.0);
            i_aff_ty=(n&32)?q(4096.0):q(-4096.0);
            i_k2=q(0.5);start_frame();
            sample_check(0,0,0);sample_check(1919,1079,0);
            sample_check(960,540,0);
            i_k2=q(-0.5);start_frame();
            sample_check(0,0,0);sample_check(1919,1079,0);
            sample_check(960,540,0);
        end
        burst_check();
        if(err==0 && checks==560 && burst_seen==8192) begin
            $display("=== ALL TESTS PASSED (err=0) ===");
            $fdisplay(fd,"=== ALL TESTS PASSED (err=0) === samples=%0d",checks);
        end else begin
            $display("=== TEST FAILED: err=%0d ===",err);
            $fdisplay(fd,"=== TEST FAILED: err=%0d samples=%0d ===",err,checks);
        end
        $fclose(trace_fd);$fclose(fd);$finish;
    end
endmodule
