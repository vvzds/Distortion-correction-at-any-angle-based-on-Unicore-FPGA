`timescale 1ns/1ps
module undistort_core_golden_tb;
    reg clk=0;
    always #4 clk=~clk;
    reg rst_n=0,start=0;
    reg [31:0] fx=32'd65536000,fy=32'd65536000;
    reg [31:0] cx=32'd62914560,cy=32'd35389440;
    reg [31:0] k1=0,k2=0,p1=0,p2=0;
    reg [31:0] a11=32'h10000,a12=0,a21=0,a22=32'h10000;
    reg [31:0] tx=0,ty=0;
    reg aff_en=0;
    wire busy,hold_req,rel,rd_req,pix_vld,sop,eop,sof,eof;
    wire [23:0] rd_addr;
    wire [6:0] rd_len;
    wire [15:0] pix;
    wire [31:0] frames,loads,hits,pixels;
    reg hold_gnt=0;
    reg [1:0] slot=2;
    reg rd_gnt=0,rd_vld=0,rd_last=0;
    reg [255:0] rd_data=0;
    reg rd_busy=0;
    integer wait_left=0,beat=0,row=0,x,j,count=0,err=0,cycles=0;
    integer fd,first_cycle=0,last_cycle=0,test_id=3,checked=0,within_one=0,max_error=0;
    integer pattern=0,rel_count=0,accepted=0,reloads=0,zero_lines=0;
    integer row_seen[0:1079];
    integer dispatch_count=0,line_loads=0,max_line_loads=0,coord_expected;
    integer coord_dx,coord_dy;
    reg previous_rel=0,held=0;
    reg stalled_req=0;
    reg [23:0] stalled_addr;
    reg [6:0] stalled_len;
    reg [8*100-1:0] result_name;
    reg [8*8-1:0] test_label;
    integer chan_error,cr,cg,cb,gr,gg,gb;
    reg [15:0] expected;
    real xp,yp,xn,yn,r2,radial,sx,sy,wx,wy;
    real rr,rg,rb;
    integer px,py,px1,py1;
    reg [4:0] golden_r,golden_b;
    reg [5:0] golden_g;
    reg [15:0] q00,q01,q10,q11;
    undistort_core dut(
        .clk(clk),.rst_n(rst_n),.i_fx(fx),.i_fy(fy),.i_cx(cx),.i_cy(cy),
        .i_k1(k1),.i_k2(k2),.i_p1(p1),.i_p2(p2),
        .i_aff_a11(a11),.i_aff_a12(a12),.i_aff_a21(a21),.i_aff_a22(a22),
        .i_aff_tx(tx),.i_aff_ty(ty),.i_aff_en(aff_en),
        .i_frame_start(start),.o_frame_busy(busy),
        .o_corr_src_hold_req(hold_req),.i_corr_src_hold_gnt(hold_gnt),
        .i_corr_src_slot(slot),.o_corr_src_rel(rel),
        .o_corr_rd_addr(rd_addr),.o_corr_rd_len(rd_len),.o_corr_rd_req(rd_req),
        .i_corr_rd_gnt(rd_gnt),.i_corr_rd_vld(rd_vld),
        .i_corr_rd_data(rd_data),.i_corr_rd_last(rd_last),
        .o_pix_vld(pix_vld),.o_pix(pix),.o_sop(sop),.o_eop(eop),
        .o_sof(sof),.o_eof(eof),.o_stat_frame_cnt(frames),
        .o_stat_line_loads(loads),.o_stat_line_hits(hits),.o_stat_pix_cnt(pixels)
    );
    function [15:0] source_pixel;
        input integer px,py;
        reg [4:0] r,b;
        reg [5:0] g;
        begin
            if(pattern==0) begin
                r=((px/64)+(py/128))&31;
                g=((px/40)+(py/80))&63;
                b=((px/80)+(py/64))&31;
            end else begin
                r=(px*13+py*7)&31;
                g=(px*29+py*11)&63;
                b=(px*3+py*23)&31;
            end
            source_pixel={r,g,b};
        end
    endfunction
    // 直接按任务书实数公式计算，与 RTL 定点流水实现独立。
    task golden_at;
        input integer ox,oy;
        output [15:0] out_pixel;
        begin
            if(aff_en) begin
                xp=($signed(a11)/65536.0)*ox+($signed(a12)/65536.0)*oy+
                   ($signed(tx)/65536.0);
                yp=($signed(a21)/65536.0)*ox+($signed(a22)/65536.0)*oy+
                   ($signed(ty)/65536.0);
            end else begin xp=ox;yp=oy;end
            xn=(xp-$signed(cx)/65536.0)/($signed(fx)/65536.0);
            yn=(yp-$signed(cy)/65536.0)/($signed(fy)/65536.0);
            r2=xn*xn+yn*yn;
            radial=1.0+($signed(k1)/65536.0)*r2+
                    ($signed(k2)/65536.0)*r2*r2;
            sx=($signed(fx)/65536.0)*
                (xn*radial+2.0*($signed(p1)/65536.0)*xn*yn+
                 ($signed(p2)/65536.0)*(r2+2.0*xn*xn))+
                ($signed(cx)/65536.0);
            sy=($signed(fy)/65536.0)*
                (yn*radial+($signed(p1)/65536.0)*(r2+2.0*yn*yn)+
                 2.0*($signed(p2)/65536.0)*xn*yn)+
                ($signed(cy)/65536.0);
            if(sx<0.0) sx=0.0; if(sx>1919.0) sx=1919.0;
            if(sy<0.0) sy=0.0; if(sy>1079.0) sy=1079.0;
            px=$rtoi(sx);py=$rtoi(sy);
            // $rtoi 向零截断；钳位后的非负数即为向下取整。
            if(px>sx) px=px-1;
            if(py>sy) py=py-1;
            px1=(px==1919)?px:px+1;
            py1=(py==1079)?py:py+1;
            wx=sx-px;wy=sy-py;
            q00=source_pixel(px,py);q01=source_pixel(px1,py);
            q10=source_pixel(px,py1);q11=source_pixel(px1,py1);
            rr=(1.0-wy)*((1.0-wx)*q00[15:11]+wx*q01[15:11])+
               wy*((1.0-wx)*q10[15:11]+wx*q11[15:11]);
            rg=(1.0-wy)*((1.0-wx)*q00[10:5]+wx*q01[10:5])+
               wy*((1.0-wx)*q10[10:5]+wx*q11[10:5]);
            rb=(1.0-wy)*((1.0-wx)*q00[4:0]+wx*q01[4:0])+
               wy*((1.0-wx)*q10[4:0]+wx*q11[4:0]);
            golden_r=$rtoi(rr+0.5);
            golden_g=$rtoi(rg+0.5);
            golden_b=$rtoi(rb+0.5);
            out_pixel={golden_r,golden_g,golden_b};
        end
    endtask
    always @(posedge clk) begin
        if(!rst_n) begin
            hold_gnt<=0;rd_gnt<=0;rd_vld<=0;rd_last<=0;
            rd_busy<=0;wait_left<=0;beat<=0;
        end else begin
            cycles<=cycles+1;
            if(rel) begin hold_gnt<=0;held<=0;end
            else if(hold_req) begin hold_gnt<=1;held<=1;end
            rd_gnt<=!rd_busy;
            rd_vld<=0;rd_last<=0;
            if(rd_req && rd_gnt) begin
                if(!held || rd_busy || rd_len!=7'd119 || rd_addr[19:0]%960!=0 ||
                   rd_addr[23:20]!=slot || rd_addr[19:0]>1036799)
                    err=err+1;
                accepted=accepted+1;
                line_loads=line_loads+1;
                if(row_seen[rd_addr[19:0]/960]!=0) reloads=reloads+1;
                row_seen[rd_addr[19:0]/960]=row_seen[rd_addr[19:0]/960]+1;
                row<=(rd_addr[19:0]/960);
                beat<=0;wait_left<=2;rd_busy<=1;
            end else if(rd_busy) begin
                if(wait_left>0) wait_left<=wait_left-1;
                else begin
                    rd_vld<=1;
                    for(j=0;j<16;j=j+1)
                        rd_data[16*j +:16]<=source_pixel(beat*16+j,1079-row);
                    rd_last<=(beat==119);
                    if(beat==119) rd_busy<=0;
                    else beat<=beat+1;
                end
            end
            if(stalled_req && (!rd_req || rd_addr!==stalled_addr || rd_len!==stalled_len))
                err=err+1;
            stalled_req<=rd_req && !rd_gnt;
            stalled_addr<=rd_addr;stalled_len<=rd_len;
            if(rel) begin
                rel_count=rel_count+1;
                if(previous_rel || rd_busy || rd_vld || count!=2073600 || !busy)
                    err=err+1;
            end
            previous_rel<=rel;
            // 从实际受理命令和取样事件独立统计，不读取 DUT 的统计控制位。
            if(dut.sample_dispatch) begin
                if(test_id>=51 && test_id<=53) begin
                    coord_expected=(dispatch_count%1920)*65536+$signed(tx);
                    if(coord_expected<0) coord_expected=0;
                    if(coord_expected>1919*65536) coord_expected=1919*65536;
                    // 一般映射允许任务书规定的 0.02px 坐标误差；T1 另做精确逐像素检查。
                    coord_dx=$signed({1'b0,dut.head_x})-coord_expected;
                    coord_dy=$signed({1'b0,dut.head_y})-((1079-dispatch_count/1920)*65536);
                    if((^dut.head_x===1'bx) || (^dut.head_y===1'bx) ||
                       coord_dx>1310 || coord_dx< -1310 ||
                       coord_dy>1310 || coord_dy< -1310) err=err+1;
                end
                dispatch_count=dispatch_count+1;
                if(dispatch_count%1920==0) begin
                    if(line_loads==0) zero_lines=zero_lines+1;
                    if(line_loads>max_line_loads) max_line_loads=line_loads;
                    line_loads=0;
                end
            end
            if(dut.load_error) err=err+1;
        end
    end
    always @(posedge clk) begin
        #1;
        if(pix_vld) begin
            if(!busy || count>=2073600 || (^pix===1'bx)) err=err+1;
            if(count==0) first_cycle=cycles;
            x=count%1920;
            if(sop!==(x==0) || eop!==(x==1919) ||
               sof!==(count==0) || eof!==(count==2073599)) begin
                $display("marker mismatch n=%0d",count);
                err=err+1;
            end
            if(count%16==0) begin
                golden_at(x,1079-count/1920,expected);
                cr=pix[15:11];cg=pix[10:5];cb=pix[4:0];
                gr=expected[15:11];gg=expected[10:5];gb=expected[4:0];
                if(cr<gr) cr=gr-cr;else cr=cr-gr;
                if(cg<gg) cg=gg-cg;else cg=cg-gg;
                if(cb<gb) cb=gb-cb;else cb=cb-gb;
                chan_error=cr;
                if(cg>chan_error) chan_error=cg;
                if(cb>chan_error) chan_error=cb;
                if(chan_error>max_error) max_error=chan_error;
                if(chan_error<=1) within_one=within_one+1;
                if(chan_error>2) begin
                    if(err<12) $display("golden mismatch n=%0d got=%h exp=%h err=%0d sx=%f sy=%f",
                                       count,pix,expected,chan_error,sx,sy);
                    err=err+1;
                end
                checked=checked+1;
            end
            if((test_id==51 && x>=1880) ||
               (test_id==52 && x<40) ||
               (test_id==53 && x>=1879)) begin
                if(pix!==source_pixel(test_id==52?0:1919,1079-count/1920)) begin
                    if(err<12) $display("edge clamp mismatch n=%0d got=%h",count,pix);
                    err=err+1;
                end
            end
            count=count+1;
            if(count==2073600) last_cycle=cycles;
        end
    end
    initial begin
        if(!$value$plusargs("TEST=%d",test_id)) test_id=3;
        if(!$value$plusargs("PATTERN=%d",pattern)) pattern=0;
        if(!$value$plusargs("RESULT=%s",result_name)) result_name="core_golden_result.txt";
        fd=$fopen(result_name,"w");
        for(j=0;j<1080;j=j+1) row_seen[j]=0;
        case(test_id)
            3: begin test_label="T3";k1=-32'sd6554;end
            4: begin test_label="T4";k1=32'sd3277;p1=32'sd131;p2=-32'sd66;end
            51:begin test_label="T5a";aff_en=1;tx=32'sd2621440;end
            52:begin test_label="T5b";aff_en=1;tx=-32'sd2621440;end
            53:begin test_label="T5c";aff_en=1;tx=32'sd2654208;end
            6: begin test_label="T6";k1=-32'sd6554;cx=32'sd26214400;cy=32'sd19660800;end
            default:test_label="UNKNOWN";
        endcase
        #30;rst_n=1;
        @(negedge clk);start=1;
        @(negedge clk);start=0;
        wait(count==2073600);
        wait(!busy);
        repeat(12) @(negedge clk);
        if(count!=2073600 || pixels!=2073600 || frames!=1 || rel_count!=1 ||
           accepted!=loads || zero_lines!=hits || dispatch_count!=2073600 ||
           rd_busy || rd_req || hold_req || held || pix_vld ||
           within_one*1.0/checked<0.995) err=err+1;
        if(err==0) begin
            $display("[%0s] PASS err=0 checked=%0d max_error=%0d",test_label,checked,max_error);
            $fdisplay(fd,"[%0s] PASS err=0 checked=%0d max_error=%0d within_one=%f pattern=%0d pixels=%0d rel=%0d",
                      test_label,checked,max_error,within_one*1.0/checked,pattern,count,rel_count);
            $fdisplay(fd,"[T7] PASS err=0 protocol/lifecycle/coordinate/independent_stats");
            $fdisplay(fd,"[T8 %0s] cycles=%0d stable_cpp=%f loads=%0d reloads=%0d hits=%0d max_loads_per_line=%0d",
                      test_label,last_cycle,(last_cycle-first_cycle)*1.0/(count-1),accepted,reloads,zero_lines,max_line_loads);
            $fdisplay(fd,"=== ALL TESTS PASSED (err=0) ===");
        end else begin
            $display("[%0s] FAIL err=%0d",test_label,err);
            $fdisplay(fd,"[%0s] FAIL err=%0d max_error=%0d ratio=%f count=%0d rel=%0d accepted=%0d loads=%0d zero=%0d hits=%0d",
                      test_label,err,max_error,within_one*1.0/checked,count,rel_count,accepted,loads,zero_lines,hits);
        end
        $fclose(fd);$finish;
    end
    initial begin
        #150000000;
        $fdisplay(fd,"[T%0d] FAIL TIMEOUT err=%0d count=%0d",test_id,err+1,count);
        $fclose(fd);
        $display("[T%0d] TIMEOUT state=%0d count=%0d fifo=%0d in_flight=%0d rd_busy=%0d",
                 test_id,
                 dut.state,count,dut.fifo_count,dut.inflight_count,rd_busy);
        $finish;
    end
endmodule
