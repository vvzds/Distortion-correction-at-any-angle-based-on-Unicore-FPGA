`timescale 1ns/1ps
module core30_system_tb;
    wire sink_ready;
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
    wire rd_gnt,rd_vld,rd_last;
    wire [255:0] rd_data;
    reg rd_busy=0,first_return=0;
    integer wait_left=0,beat=0,row=0,x,j,count=0,err=0,cycles=0;
    integer first_x=0,burst_last=0,ddr_wait=2,frame_start_cycle=0;
    integer payload_beats=0,actual_first_delay=0,accept_cycle=0,max_delay=0;
    integer grant_wait=0,grant_age=0;
    integer ddr_gap=0, gap_left=0, random_seed=731;
    integer stall_fifo=0,stall_prep=0,stall_data=0,stall_phase=0;
    integer check_stride=16;
    wire [31:0] seg_loads;
    wire line_stats_valid;
`ifdef AB_CANDIDATE


`else
    assign seg_loads=0;
    assign line_stats_valid=1;
`endif
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
    undistort_core #(.USE_SINK_CREDIT(1)) dut(
        .clk(clk),.rst_n(rst_n),.i_sink_ready(sink_ready),.i_fx(fx),.i_fy(fy),.i_cx(cx),.i_cy(cy),
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
`ifdef AB_CANDIDATE
        ,.o_stat_seg_loads(seg_loads),.o_stat_line_stats_valid(line_stats_valid)
`endif
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
            hold_gnt<=0;

        end else begin
            cycles<=cycles+1;
            if(rel) begin hold_gnt<=0;held<=0;end
            else if(hold_req) begin hold_gnt<=1;held<=1;end
            if(busy && dut.state==4)begin
                if(dut.fifo_count==0)stall_fifo=stall_fifo+1;
`ifdef AB_CANDIDATE
                else if(!dut.identity_mode && dut.prepared_count==dut.consumed_count)stall_prep=stall_prep+1;
                else if(!dut.identity_mode && !dut.ids_ready)stall_data=stall_data+1;
`endif
                else if(dut.identity_mode && dut.sample_phase)stall_phase=stall_phase+1;
            end
            if(rd_req && rd_gnt)begin
                first_return=1;
                if(!held || (rd_len!=7'd119 && rd_len!=7'd7) || rd_addr[2:0]!=0 ||
                   (rd_addr[19:0]%960)/8+rd_len+1>120 ||
                   rd_addr[23:20]!=slot || rd_addr[19:0]>1036799)err=err+1;
                accepted=accepted+1;
                if(rd_len==119)line_loads=line_loads+1;
                if(row_seen[rd_addr[19:0]/960]!=0)reloads=reloads+1;
                row_seen[rd_addr[19:0]/960]=row_seen[rd_addr[19:0]/960]+1;
                accept_cycle=cycles;
            end
            if(rd_vld)begin
                payload_beats=payload_beats+1;
                if(first_return)begin
                    first_return=0;
                    actual_first_delay=cycles-accept_cycle;
                    if(actual_first_delay>max_delay)max_delay=actual_first_delay;
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

    // 使用生产读桥、写FIFO、打包及仲裁器；共享串行DDR服务模型。
    // 模型不替代厂商DDR时序仿真，原始图由独立函数生成。
    wire [27:0] araddr,awaddr;
    wire [3:0] arlen,arid,awlen,awid;
    wire arvalid,awvalid;
    reg arready=0,awready=0,rv=0,rl=0,wp=0,wl=0;
    reg [255:0] rdata=0;
    reg [3:0] rid=0;
    wire [255:0] wdata;
    wire [31:0] wstrb;
    reg disp_valid=0,raw_valid=0;
    reg [27:0] disp_addr=28'h600000,raw_addr=0;
    wire disp_ready,disp_vld,raw_ready,raw_pull,raw_last;
    integer disp_due=0,raw_due=0,disp_reads=0,raw_writes=0;
    integer mem_mode=0,mem_left=0,mem_wait=0,mem_gap=0;
    integer mem_row=0,mem_x=0,mem_i=0,mem_beat=0,service_turn=0;
    integer fifo_highwater=0,sink_pause_cycles=0;
    integer write_pixels=0,published=0,publish_cycle=0,score_count=0;
    reg [15:0] output_score[0:2073599];
    wire wr_slot_req,wr_req,wr_gnt,wr_commit,pack_idle,publish,pack_error;
    wire [23:0] wr_addr,pack_addr;
    wire [31:0] wr_data;
    wire [3:0] pack_len;
    wire pack_valid,pack_ready,pack_pull,pack_last;
    wire [255:0] pack_data;
    wire slot_gnt=wr_slot_req && pack_idle;
    rect_wr_if writer(.o_pix_ready(sink_ready),.clk(clk),.rst_n(rst_n),.i_pix_vld(pix_vld),.i_pix(pix),
        .i_sop(sop),.i_eop(eop),.i_sof(sof),.i_eof(eof),
        .o_corr_wr_slot_req(wr_slot_req),.i_corr_wr_slot_gnt(slot_gnt),
        .i_corr_wr_slot(3'd4),.o_corr_wr_commit(wr_commit),
        .o_corr_wr_req(wr_req),.o_corr_wr_addr(wr_addr),.o_corr_wr_data(wr_data),.i_corr_wr_gnt(wr_gnt));
    corr_write_pack packer(.clk(clk),.rst_n(rst_n),.begin_frame(slot_gnt),.frame_slot(3'd4),
        .corr_wr_req(wr_req),.corr_wr_addr(wr_addr),.corr_wr_data(wr_data),.corr_wr_gnt(wr_gnt),
        .corr_wr_commit(wr_commit),.frame_idle(pack_idle),.publish(publish),.protocol_error(pack_error),
        .awaddr(pack_addr),.awlen(pack_len),.awvalid(pack_valid),.awready(pack_ready),
        .wdata(pack_data),.wpull(pack_pull),.wlast(pack_last));
    corr_write_arb wa(.clk(clk),.rst_n(rst_n),.raw_awaddr(raw_addr),.raw_awlen(4'd7),
        .raw_awid(4'd0),.raw_awvalid(raw_valid),.raw_awready(raw_ready),.raw_wpull(raw_pull),.raw_wlast(raw_last),
        .raw_wdata(256'd0),.raw_wstrb(32'hffffffff),.corr_awaddr(pack_addr),.corr_awlen(pack_len),
        .corr_awvalid(pack_valid),.corr_awready(pack_ready),.corr_wpull(pack_pull),.corr_wlast(pack_last),
        .corr_wdata(pack_data),.axi_awaddr(awaddr),.axi_awlen(awlen),.axi_awid(awid),.axi_awvalid(awvalid),
        .axi_awready(awready),.axi_wdata(wdata),.axi_wstrb(wstrb),.axi_wpull(wp),.axi_wlast(wl));
    corr_read_bridge read_bridge(.clk(clk),.rst_n(rst_n),.corr_rd_req(rd_req),.corr_rd_addr(rd_addr),.corr_rd_len(rd_len),
        .corr_rd_gnt(rd_gnt),.corr_rd_vld(rd_vld),.corr_rd_last(rd_last),.corr_rd_data(rd_data),
        .disp_araddr(disp_addr),.disp_arlen(4'd7),.disp_arvalid(disp_valid),.disp_arready(disp_ready),.disp_rvalid(disp_vld),
        .axi_araddr(araddr),.axi_arid(arid),.axi_arlen(arlen),.axi_arvalid(arvalid),.axi_arready(arready),
        .axi_rdata(rdata),.axi_rvalid(rv),.axi_rlast(rl),.axi_rid(rid));
    // 1920x1080 RGB565、30fps的显示读/采集写：每256拍8个256bit数据拍。
    // 请求一旦发出保持至握手；若服务落后则累积欠款，不静默丢弃。
    always @(posedge clk)if(rst_n)begin
        if(writer.fifo_count>fifo_highwater)fifo_highwater=writer.fifo_count;
        if(!sink_ready && busy)sink_pause_cycles=sink_pause_cycles+1;
        if(cycles%256==0)begin disp_due=disp_due+1;raw_due=raw_due+1;end
        if(disp_valid && disp_ready)begin disp_due=disp_due-1;disp_addr<=disp_addr+64;end
        if(raw_valid && raw_ready)begin raw_due=raw_due-1;raw_addr<=raw_addr+64;end
        disp_valid<=disp_due>0;raw_valid<=raw_due>0;
        if(disp_vld)disp_reads=disp_reads+1;
        if(raw_pull)raw_writes=raw_writes+1;
        if(pix_vld)begin output_score[score_count]=pix;score_count=score_count+1;end
        if(pack_pull)begin
            for(mem_i=0;mem_i<16;mem_i=mem_i+1)begin
                if(write_pixels>=score_count || wdata[mem_i*16+:16]!==output_score[write_pixels])begin
                    if(err<12)$display("write scoreboard mismatch pixel=%0d got=%h expected=%h",write_pixels,wdata[mem_i*16+:16],output_score[write_pixels]);err=err+1;
                end
                write_pixels=write_pixels+1;
            end
        end
        if(pack_error || writer.fault)begin $fdisplay(fd,"FAIL writer fault cycle=%0d pixels=%0d written=%0d pack=%b input=%b overflow=%b queue=%b slot=%b fifo=%0d",cycles,score_count,write_pixels,pack_error,writer.input_error,writer.overflow,writer.queue_error,writer.slot_error,writer.fifo_count);
            $fflush(fd);err=err+1;$finish;end
        if(publish)begin
            published=published+1;publish_cycle=cycles;
            if(write_pixels!=2073600 || busy)err=err+1;
        end
    end
    // 负沿驱动，避免与DUT采样竞争。读写共用一个服务端，突发间轮转公平仲裁。
    always @(negedge clk)begin
        arready=0;awready=0;rv=0;rl=0;wp=0;wl=0;
        if(rst_n)begin
            if(mem_mode==0)begin
                if(arvalid && (!awvalid || service_turn==0))begin
                    arready=1;mem_mode=1;rid=arid;mem_left=arlen+1;
                    mem_row=(araddr%1048576)/960;mem_x=((araddr%1048576)%960)*2;
                    mem_beat=0;mem_wait=ddr_wait;service_turn=1;
                end else if(awvalid)begin
                    awready=1;mem_mode=2;mem_left=awlen+1;
                    mem_wait=grant_wait;service_turn=0;
                end
            end else if(mem_wait>0)mem_wait=mem_wait-1;
            else if(mem_gap>0)mem_gap=mem_gap-1;
            else begin
                if(mem_mode==1)begin
                    rv=1;rl=(mem_left==1);
                    for(j=0;j<16;j=j+1)rdata[j*16+:16]=source_pixel(mem_x+mem_beat*16+j,1079-mem_row);
                end else begin wp=1;wl=(mem_left==1);end
                mem_left=mem_left-1;mem_beat=mem_beat+1;
                if(mem_left==0)mem_mode=0;
                else if(ddr_gap!=0)mem_gap=($random(random_seed)&32'h7fffffff)%(ddr_gap+1);
            end
        end
    end
    // 固定内部保护窗口的可执行断言，不把10bit序号拓展为任意长度接口保证。
    always @(posedge clk)if(rst_n && busy && dut.state!=1)begin
        if(dut.headq_count>4 || dut.prepared_count-dut.consumed_count>256 ||
           dut.consumed_count-dut.retired_count>5 || dut.fifo_count+dut.inflight_count>480)begin
            if(err<12)$display("internal bounded-window invariant failed");err=err+1;
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
            if(test_id==0 && pix!==source_pixel(x,1079-count/1920))begin
                if(err<12)$display("identity exact mismatch n=%0d got=%h",count,pix);
                err=err+1;
            end
            if(count%check_stride==0) begin
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
            0: begin test_label="IDENTITY";end
            10,11,12: begin
                test_label="REAL";
                fx=32'sd98809312;fy=32'sd98789197;
                cx=32'sd57903224;cy=32'sd37269520;
                k1=-32'sd25001;k2=32'sd10269;p1=-32'sd20;p2=-32'sd7;
                if(test_id==11)begin aff_en=1;tx=32'sd1572864;end
                if(test_id==12)begin aff_en=1;tx=-32'sd1572864;end
            end
            20:begin test_label="ROT1";aff_en=1;
        fx=32'sd98809312;fy=32'sd98789197;cx=32'sd57903224;cy=32'sd37269520;
        k1=-32'sd25001;k2=32'sd10269;p1=-32'sd20;p2=-32'sd7;
        a11=32'sd65526;a12=-32'sd1144;a21=32'sd1144;a22=32'sd65526;
        tx=32'sd626783;ty=-32'sd1092273;end
21:begin test_label="ROT5";aff_en=1;
        fx=32'sd98809312;fy=32'sd98789197;cx=32'sd57903224;cy=32'sd37269520;
        k1=-32'sd25001;k2=32'sd10269;p1=-32'sd20;p2=-32'sd7;
        a11=32'sd65287;a12=-32'sd5712;a21=32'sd5712;a22=32'sd65287;
        tx=32'sd3320540;ty=-32'sd5346328;end
22:begin test_label="ROT15";aff_en=1;
        fx=32'sd98809312;fy=32'sd98789197;cx=32'sd57903224;cy=32'sd37269520;
        k1=-32'sd25001;k2=32'sd10269;p1=-32'sd20;p2=-32'sd7;
        a11=32'sd63303;a12=-32'sd16962;a21=32'sd16962;a22=32'sd63303;
        tx=32'sd11293562;ty=-32'sd15070336;end
23:begin test_label="ROT90";aff_en=1;
        fx=32'sd98809312;fy=32'sd98789197;cx=32'sd57903224;cy=32'sd37269520;
        k1=-32'sd25001;k2=32'sd10269;p1=-32'sd20;p2=-32'sd7;
        a11=32'sd0;a12=-32'sd65536;a21=32'sd65536;a22=32'sd0;
        tx=32'sd98238464;ty=-32'sd27525120;end
24:begin test_label="ROT30";aff_en=1;
        fx=32'sd98809312;fy=32'sd98789197;cx=32'sd57903224;cy=32'sd37269520;
        k1=-32'sd25001;k2=32'sd10269;p1=-32'sd20;p2=-32'sd7;
        a11=32'sd56756;a12=-32'sd32768;a21=32'sd32768;a22=32'sd56756;
        tx=32'sd26392180;ty=-32'sd23958534;end
25:begin test_label="ROT45";aff_en=1;
        fx=32'sd98809312;fy=32'sd98789197;cx=32'sd57903224;cy=32'sd37269520;
        k1=-32'sd25001;k2=32'sd10269;p1=-32'sd20;p2=-32'sd7;
        a11=32'sd46341;a12=-32'sd46341;a21=32'sd46341;a22=32'sd46341;
        tx=32'sd43312976;ty=-32'sd30027845;end
            default:test_label="UNKNOWN";
        endcase
        if($value$plusargs("DDR_WAIT=%d",ddr_wait))begin end
        if($value$plusargs("DDR_GAP=%d",ddr_gap))begin end
        if($value$plusargs("GRANT_WAIT=%d",grant_wait))begin end
        if($value$plusargs("STRIDE=%d",check_stride))begin end
        #30;rst_n=1;
        @(negedge clk);start=1;frame_start_cycle=cycles;
        @(negedge clk);start=0;
        wait(count==2073600);
        wait(!busy);
        wait(published==1);
        repeat(12) @(negedge clk);
        if(count!=2073600 || pixels!=2073600 || frames!=1 || rel_count!=1 ||
           accepted!=loads+seg_loads || (line_stats_valid && zero_lines!=hits) || dispatch_count!=2073600 ||
           rd_busy || rd_req || hold_req || held || pix_vld ||
           within_one*1.0/checked<0.995) err=err+1;
        $fdisplay(fd,"METRIC frame_cycles=%0d stable_cycles=%0d total_cpp=%f modeled_fps=%f commands=%0d segments=%0d lines=%0d beats=%0d max_first_delay=%0d stall_fifo=%0d stall_prep=%0d stall_data=%0d stall_phase=%0d",
            last_cycle-frame_start_cycle,last_cycle-first_cycle+1,
            (last_cycle-frame_start_cycle)*1.0/2073600,125000000.0/(last_cycle-frame_start_cycle),
            accepted,seg_loads,loads,payload_beats,max_delay,stall_fifo,stall_prep,stall_data,stall_phase);
        $fdisplay(fd,"SYSTEM fifo_highwater=%0d sink_pause_cycles=%0d",fifo_highwater,sink_pause_cycles);
        $fdisplay(fd,"SYSTEM publish_cycles=%0d modeled_fps=%f written_pixels=%0d display_beats=%0d capture_beats=%0d display_debt=%0d capture_debt=%0d",publish_cycle-frame_start_cycle,125000000.0/(publish_cycle-frame_start_cycle),write_pixels,disp_reads,raw_writes,disp_due,raw_due);
        if(published!=1 || write_pixels!=2073600 || disp_due>2 || raw_due>2)err=err+1;
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
        #500000000;
        $fdisplay(fd,"[T%0d] FAIL TIMEOUT err=%0d count=%0d accepted=%0d seg_loads=%0d beats=%0d stall_fifo=%0d stall_prep=%0d stall_data=%0d stall_phase=%0d prepared=%0d consumed=%0d retired=%0d fetch_count=%0d",test_id,err+1,count,accepted,seg_loads,payload_beats,stall_fifo,stall_prep,stall_data,stall_phase,dut.prepared_count,dut.consumed_count,dut.retired_count,dut.u_cache.fetch_count);
        $fclose(fd);
        $display("[T%0d] TIMEOUT state=%0d count=%0d fifo=%0d in_flight=%0d rd_busy=%0d",
                 test_id,
                 dut.state,count,dut.fifo_count,dut.inflight_count,rd_busy);
        $finish;
    end
endmodule
