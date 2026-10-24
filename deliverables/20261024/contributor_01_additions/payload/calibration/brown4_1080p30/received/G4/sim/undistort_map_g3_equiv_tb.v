`timescale 1ns/1ps
// G3附加性质测试：与已验收V1.2按有效事务顺序逐位比较，不替代独立real golden。
module undistort_map_g3_equiv_tb;
    reg clk=0,rst_n=0,init=0,valid=0,aff_en=0;
    always #4 clk=~clk;
    reg signed [31:0] fx,fy,cx,cy,k1,k2,p1,p2;
    reg signed [31:0] a11,a12,a21,a22,tx,ty;
    reg [10:0] u=0,v=0;
    wire ready_old,ready_new,valid_old,valid_new;
    wire [26:0] x_old,y_old,x_new,y_new;
    reg [26:0] expected_x [0:65535],expected_y [0:65535];
    reg [3:0] valid_delay;
    integer wr=0,rd=0,err=0,fd,frame_no,n,timer,seed=76813,sent=0;

    undistort_map dut(
        .clk(clk),.rst_n(rst_n),.i_frame_init(init),
        .i_fx(fx),.i_fy(fy),.i_cx(cx),.i_cy(cy),
        .i_k1(k1),.i_k2(k2),.i_p1(p1),.i_p2(p2),
        .i_aff_a11(a11),.i_aff_a12(a12),.i_aff_a21(a21),.i_aff_a22(a22),
        .i_aff_tx(tx),.i_aff_ty(ty),.i_aff_en(aff_en),
        .o_init_done(ready_new),.i_valid(valid),.i_u(u),.i_v(v),
        .o_valid(valid_new),.o_sx_q16(x_new),.o_sy_q16(y_new)
    );
    undistort_map_v12_ref accepted(
        .clk(clk),.rst_n(rst_n),.i_frame_init(init),
        .i_fx(fx),.i_fy(fy),.i_cx(cx),.i_cy(cy),
        .i_k1(k1),.i_k2(k2),.i_p1(p1),.i_p2(p2),
        .i_aff_a11(a11),.i_aff_a12(a12),.i_aff_a21(a21),.i_aff_a22(a22),
        .i_aff_tx(tx),.i_aff_ty(ty),.i_aff_en(aff_en),
        .o_init_done(ready_old),.i_valid(valid),.i_u(u),.i_v(v),
        .o_valid(valid_old),.o_sx_q16(x_old),.o_sy_q16(y_old)
    );

    always @(posedge clk) begin
        #1;
        if(!rst_n) begin
            valid_delay=0;
            if(valid_new || valid_old) err=err+1;
        end else begin
            if(ready_new!==ready_old || valid_new!==valid_delay[3]) begin
                if(err<8) $fdisplay(fd,"FAIL handshake frame=%0d old=%b new=%b expected=%b",
                                      frame_no,valid_old,valid_new,valid_delay[3]);
                err=err+1;
            end
            valid_delay={valid_delay[2:0],valid_old};
            if(valid_old) begin
                if(wr>=65536) err=err+1;
                else begin expected_x[wr]=x_old;expected_y[wr]=y_old;end
                wr=wr+1;
            end
            if(valid_new) begin
                if(rd>=wr || x_new!==expected_x[rd] || y_new!==expected_y[rd]) begin
                    if(err<8) $fdisplay(fd,"FAIL coord frame=%0d sample=%0d old=(%h,%h) new=(%h,%h)",
                                          frame_no,rd,expected_x[rd],expected_y[rd],x_new,y_new);
                    err=err+1;
                end
                rd=rd+1;
            end
        end
    end

    initial begin
        fd=$fopen("map_g3_equiv_result.txt","w");
        fx=32'd65536000;fy=fx;cx=32'd62914560;cy=32'd35389440;
        k1=0;k2=0;p1=0;p2=0;
        a11=32'sh10000;a12=0;a21=0;a22=32'sh10000;tx=0;ty=0;
        repeat(4) @(negedge clk);rst_n=1;
        for(frame_no=0;frame_no<128;frame_no=frame_no+1) begin
            @(negedge clk);
            if(frame_no<32) begin
                fx=32'd8388608+(($random(seed)&32'h7fffffff)%200000000);
                fy=32'd8388608+(($random(seed)&32'h7fffffff)%200000000);
                cx=($random(seed)&32'h7fffffff)%125763585;
                cy=($random(seed)&32'h7fffffff)%70713345;
                k1=(($random(seed)&32'h7fffffff)%65537)-32768;
                k2=(($random(seed)&32'h7fffffff)%65537)-32768;
                p1=(($random(seed)&32'h7fffffff)%1311)-655;
                p2=(($random(seed)&32'h7fffffff)%1311)-655;
                a11=(($random(seed)&32'h7fffffff)%262145)-131072;
                a12=(($random(seed)&32'h7fffffff)%262145)-131072;
                a21=(($random(seed)&32'h7fffffff)%262145)-131072;
                a22=(($random(seed)&32'h7fffffff)%262145)-131072;
                tx=(($random(seed)&32'h7fffffff)%536870913)-268435456;
                ty=(($random(seed)&32'h7fffffff)%536870913)-268435456;
                aff_en=(frame_no%3!=0);
                if(frame_no==0 || frame_no==1) begin
                    k1=0;k2=0;p1=0;p2=0;
                    aff_en=frame_no;
                    a11=32'sh10000;a12=0;a21=0;a22=32'sh10000;tx=0;ty=0;
                end
            end else begin
                fx=32'd8388608;fy=fx;cx=0;cy=0;aff_en=1;
                a11=(frame_no&1)?32'sd131072:-32'sd131072;
                a12=(frame_no&2)?32'sd131072:-32'sd131072;
                a21=(frame_no&4)?32'sd131072:-32'sd131072;
                a22=(frame_no&8)?32'sd131072:-32'sd131072;
                tx=(frame_no&16)?32'sd268435456:-32'sd268435456;
                ty=(frame_no&32)?32'sd268435456:-32'sd268435456;
                k1=-32'sd32768;k2=(frame_no&1)?32'sd32768:-32'sd32768;
                p1=32'sd655;p2=-32'sd655;
            end
            // 追加32组归一化边界：最小/最大焦距、分数主点、正负仿射偏移。
            if(frame_no>=96) begin
                fx=(frame_no&1)?32'sd8388608:32'sd2147418112;
                fy=(frame_no&2)?32'sd8388609:32'sd2147418111;
                cx=(frame_no&4)?32'sd125763583:32'sd1;
                cy=(frame_no&8)?32'sd70713343:32'sd65535;
                tx=(frame_no&16)?32'sd268435455:-32'sd268435455;
                ty=-tx;
            end
            init=1;
            @(negedge clk);init=0;
            timer=0;
            while((ready_new!==1 || ready_old!==1) && timer<120) begin
                @(negedge clk);timer=timer+1;
            end
            if(ready_new!==1 || ready_old!==1) err=err+1;
            for(n=0;n<512;n=n+1) begin
                @(negedge clk);
                valid=(frame_no>=96) || (n%7!=3 && n%7!=4);
                u=($random(seed)&32'h7fffffff)%1920;
                v=($random(seed)&32'h7fffffff)%1080;
                if(n==0) begin u=0;v=0;end
                if(n==1) begin u=1919;v=1079;end
                if(valid) sent=sent+1;
            end
            @(negedge clk);valid=0;
            repeat(16) @(negedge clk);
            if(wr!=sent || rd!=sent) err=err+1;
        end
        if(err==0 && sent>30000 && rd==sent) begin
            $fdisplay(fd,"[G3 equivalence] PASS err=0 frames=128 samples=%0d extra_latency=4",rd);
            $fdisplay(fd,"=== ALL TESTS PASSED (err=0) ===");
            $display("=== ALL TESTS PASSED (err=0) ===");
        end else $fdisplay(fd,"FAIL err=%0d sent=%0d old=%0d new=%0d",err,sent,wr,rd);
        $fclose(fd);$finish;
    end
    initial begin
        #2000000;
        $fdisplay(fd,"FAIL TIMEOUT err=%0d",err+1);$fclose(fd);$finish;
    end
endmodule
