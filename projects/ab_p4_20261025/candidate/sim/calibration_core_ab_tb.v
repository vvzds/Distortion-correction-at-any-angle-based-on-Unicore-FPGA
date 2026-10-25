`timescale 1ns/1ps
module calibration_core_ab_tb;
    `include "parameters/calibration_q16.vh"
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,start=0;
    integer mode=0,pattern=1,slotarg=2;
    reg [15:0] expected[0:2073599];
    reg [53:0] coordinates[0:2073599];
    reg [255:0] source_words[0:129599];
    reg [8*240-1:0] vector_file;
    wire busy,hold_req,rel,rd_req,pix_vld,sop,eop,sof,eof;
    wire [23:0] addr;wire [6:0] len;wire [15:0] pix;
    wire [31:0] frames,loads,hits,pixels,segments;
    wire line_stats_valid;
    integer latencyarg=0,periodarg=0,grantarg=0,gatearg=1;
    integer grant_wait=0,read_base=0,read_len=0;
    reg hold_gnt=0,rd_vld=0,rd_last=0,rd_active=0;
    wire rd_gnt=rst_n&&!rd_active&&grant_wait==0;
    reg [1:0] source_slot=2;
    reg [255:0] rd_data=0;
    integer cycles=0,first_cycle=0,last_cycle=0,accepted=0,dispatch=0;
    integer delay_count=0,beat=0,row=0,j=0,count=0,err=0,rel_count=0;
    integer first_read_row=-1,last_read_row=-1,minrow=1080,maxrow=-1;
    integer checkx,checky,ra,rb,expected_sx,expected_sy;
    reg held=0,prev_rel=0,stalled=0;
    reg [23:0] stalled_addr;reg [6:0] stalled_len;
    `include "r3_r4_core_monitor.vh"
    undistort_core #(.SIM_MODE(0),.LINES_PER_SET(2)) dut(
        .clk(clk),.rst_n(rst_n),.i_fx(CAL_FX),.i_fy(CAL_FY),.i_cx(CAL_CX),.i_cy(CAL_CY),
        .i_k1(mode==0?32'sd0:CAL_K1),.i_k2(mode==0?32'sd0:CAL_K2),
        .i_p1(mode==0?32'sd0:CAL_P1),.i_p2(mode==0?32'sd0:CAL_P2),
        .i_aff_a11(32'sh10000),.i_aff_a12(32'sd0),.i_aff_a21(32'sd0),
        .i_aff_a22(32'sh10000),.i_aff_tx(32'sd0),.i_aff_ty(32'sd0),.i_aff_en(1'b0),
        .i_frame_start(start),.o_frame_busy(busy),.o_corr_src_hold_req(hold_req),
        .i_corr_src_hold_gnt(hold_gnt),.i_corr_src_slot(source_slot),.o_corr_src_rel(rel),
        .o_corr_rd_addr(addr),.o_corr_rd_len(len),.o_corr_rd_req(rd_req),
        .i_corr_rd_gnt(rd_gnt),.i_corr_rd_vld(rd_vld),.i_corr_rd_data(rd_data),.i_corr_rd_last(rd_last),
        .o_pix_vld(pix_vld),.o_pix(pix),.o_sop(sop),.o_eop(eop),.o_sof(sof),.o_eof(eof),
        .o_stat_seg_loads(segments),.o_stat_line_stats_valid(line_stats_valid),.o_stat_frame_cnt(frames),.o_stat_line_loads(loads),.o_stat_line_hits(hits),.o_stat_pix_cnt(pixels));
    function [15:0] source_pixel;
        input integer px,py;
        reg [4:0] r,b;reg [5:0] g;
        begin
            if(pattern==0) begin
                r=((px/64)+(py/128))&31;g=((px/40)+(py/80))&63;b=((px/80)+(py/64))&31;
            end else begin
                r=(px*13+py*7)&31;g=(px*29+py*11)&63;b=(px*3+py*23)&31;
            end
            source_pixel={r,g,b};
        end
    endfunction
    always @(posedge clk) begin
        if(rst_n) begin
            cycles=cycles+1;
            if(dut.fifo_count>512 || dut.inflight_count>480 ||
               dut.fifo_count+dut.inflight_count>480)$fatal(1,"coordinate FIFO bounds");
            if(mode!=0 && (dut.consumed_count>dut.prepared_count ||
               dut.retired_count>dut.consumed_count ||
               dut.prepared_count-dut.consumed_count>256 ||
               dut.u_cache.fetch_count>192))$fatal(1,"lookahead/retirement bounds");
            if(rel) begin held<=0;hold_gnt<=0;end
            else if(hold_req) begin held<=1;hold_gnt<=1;end
            rd_vld<=0;rd_last<=0;
            if(rd_req&&!rd_active&&grant_wait>0)grant_wait<=grant_wait-1;
            if(rd_req&&rd_gnt) begin
                if(!held||rd_active||addr[23:20]!=source_slot||addr[2:0]!=0||
                    addr[19:0]>=1036800||
                    (mode==0?(len!=119||addr[19:0]%960!=0):
                             (len!=3||(addr[19:0]%960)%32!=0))||
                    (addr[19:0]%960)+(len+1)*8>960) $fatal(1,"DDR illegal addr=%h len=%0d",addr,len);
                accepted=accepted+1;
                row=addr[19:0]/960;read_base=addr[19:0]>>3;read_len=len;
                if(first_read_row<0) first_read_row=row;
                last_read_row=row;if(row<minrow)minrow=row;if(row>maxrow)maxrow=row;
                beat<=0;delay_count<=latencyarg?latencyarg-1:2+(accepted%5);rd_active<=1;
            end else if(rd_active) begin
                if(delay_count>0) delay_count<=delay_count-1;
                else if(periodarg?((cycles%periodarg)==0):((cycles%11)!=0)) begin
                    rd_vld<=1;
                    rd_data<=source_words[read_base+beat];
                    rd_last<=beat==read_len;
                    if(beat==read_len)begin rd_active<=0;grant_wait<=grantarg;end else beat<=beat+1;
                end
            end
            if(stalled&&(!rd_req||addr!==stalled_addr||len!==stalled_len)) $fatal(1,"DDR request changed while stalled");
            stalled<=rd_req&&!rd_gnt;stalled_addr<=addr;stalled_len<=len;
            if(dut.load_error) $fatal(1,"CACHE load error");
            if(dut.sample_dispatch) begin
                if(mode==0) begin expected_sx=(dispatch%1920)*65536;expected_sy=(1079-dispatch/1920)*65536;end
                else begin expected_sx=coordinates[dispatch][53:27];expected_sy=coordinates[dispatch][26:0];end
                if(dut.head_x!==expected_sx[26:0]||dut.head_y!==expected_sy[26:0]) $fatal(1,"DISPATCH coordinate mismatch n=%0d",dispatch);
                ra=1079-(expected_sy>>16);rb=ra==0?0:ra-1;
                if(dut.query_a!==ra[10:0]||dut.query_b!==rb[10:0]) $fatal(1,"DDR row flip mismatch n=%0d",dispatch);
                dispatch=dispatch+1;
            end
            if(rel) begin
                rel_count=rel_count+1;
                if(prev_rel||rd_active||rd_vld||count!=2073600||!busy) $fatal(1,"Release before complete drain");
            end
            prev_rel<=rel;
        end
    end
    always @(posedge clk) begin
        #1;
        if(pix_vld) begin
            if(count>=2073600||!busy) $fatal(1,"Extra pixel or inactive frame");
            if(pix!==expected[count]) begin
                if(err<8) $display("PIXEL_MISMATCH mode=%0d n=%0d got=%h exp=%h",mode,count,pix,expected[count]);
                err=err+1;
            end
            if(sop!==(count%1920==0)||eop!==(count%1920==1919)||sof!==(count==0)||eof!==(count==2073599)) $fatal(1,"Marker mismatch n=%0d",count);
            if(count==0) first_cycle=cycles;
            count=count+1;last_cycle=cycles;
            if(count%518400==0) $display("PROGRESS mode=%0d pattern=%0d pixels=%0d cycles=%0d",mode,pattern,count,cycles);
        end
    end
    initial begin
        if(!$value$plusargs("LATENCY=%d",latencyarg))latencyarg=0;
        if(!$value$plusargs("PERIOD=%d",periodarg))periodarg=0;
        if(!$value$plusargs("GRANT=%d",grantarg))grantarg=0;
        if(!$value$plusargs("GATE=%d",gatearg))gatearg=1;
        grant_wait=grantarg;
        if(!$value$plusargs("MODE=%d",mode))mode=0;
        if(!$value$plusargs("PATTERN=%d",pattern))pattern=1;
        if(!$value$plusargs("SLOT=%d",slotarg))slotarg=2;
        source_slot=slotarg;
        if(!$value$plusargs("VECTOR=%s",vector_file))vector_file="vectors/identity_pixels.hex";
        $readmemh(vector_file,expected);
        if(pattern==0)$readmemh("vectors/source_words_0.hex",source_words);
        else $readmemh("vectors/source_words_1.hex",source_words);
        if(mode!=0)$readmemh("vectors/map_expected.hex",coordinates);
        #30;rst_n=1;
        @(negedge clk);start=1;@(negedge clk);start=0;
        wait(busy);wait(!busy);repeat(15)@(negedge clk);
        if(err!=0||count!=2073600||dispatch!=2073600||pixels!=2073600||frames!=1||
            (mode==0?(accepted!=loads||segments!=0||!line_stats_valid):
                      (accepted!=segments||loads!=0||hits!=0||line_stats_valid))||rel_count!=1||held||rd_active||rd_req||pix_vld) $fatal(1,"CORE FAIL err=%0d count=%0d",err,count);
        $display("R3_CORE_DRAIN clears=%0d accepted=%0d returned=%0d busy_start_ignored=%0d outstanding=%0d",mon_clears,mon_accepted,mon_returned,mon_busy_starts,mon_outstanding);
        $display("R4_ACTUAL first_min=%0d first_max=%0d gap_min=%0d gap_max=%0d grant_min=%0d grant_max=%0d return_beats=%0d transactions=%0d cycles=%0d pixels=%0d mismatches=%0d",mon_first_min,mon_first_max,mon_gap_min,mon_gap_max,mon_grant_min,mon_grant_max,mon_returned,mon_accepted,cycles,count,err);
        if(mon_clears!=1 || mon_busy_starts!=1 || mon_outstanding!=0 || mon_returned!=(mode==0?120:4)*mon_accepted)$fatal(1,"R3/R4 coverage missing");
        if(gatearg && cycles>(mode==0?4166666:5000000))$fatal(1,"PERFORMANCE_GATE cycles=%0d mode=%0d",cycles,mode);
        $display("AB_STATS segments=%0d line_stats_valid=%0d latency=%0d period=%0d grant=%0d",segments,line_stats_valid,latencyarg,periodarg,grantarg);
        $display("CORE PASS mode=%0d pattern=%0d slot=%0d pixels=%0d err=0 cycles=%0d cpp=%f model_fps_125MHz=%f line_loads=%0d hits=%0d first_read=%0d last_read=%0d minrow=%0d maxrow=%0d",
            mode,pattern,source_slot,count,cycles,cycles*1.0/count,125000000.0/cycles,loads,hits,first_read_row,last_read_row,minrow,maxrow);
        $finish;
    end
    // A frame-start request while an accepted old read is delayed must not
    // clear cache state or start a new frame. No hierarchy is forced.
    initial begin
        wait(rst_n);wait(rd_active);
        @(negedge clk);start=1;@(negedge clk);start=0;
    end
    initial begin #250000000;$fatal(1,"CORE TIMEOUT pixels=%0d state=%0d",count,dut.state);end
endmodule
