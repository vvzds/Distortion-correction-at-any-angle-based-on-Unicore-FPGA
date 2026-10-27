// 单时钟域校正引擎；外部端口遵循任务书 V1.1。
module undistort_core #(
    parameter SIM_MODE = 0,
    parameter USE_SINK_CREDIT = 0,
    parameter LINES_PER_SET = 2
)(
    input wire clk, rst_n,
    input wire i_sink_ready,
    input wire signed [31:0] i_fx,i_fy,i_cx,i_cy,
    input wire signed [31:0] i_k1,i_k2,i_p1,i_p2,
    input wire signed [31:0] i_aff_a11,i_aff_a12,i_aff_a21,i_aff_a22,
    input wire signed [31:0] i_aff_tx,i_aff_ty,
    input wire i_aff_en, i_frame_start,
    output reg o_frame_busy,
    output reg o_corr_src_hold_req,
    input wire i_corr_src_hold_gnt,
    input wire [1:0] i_corr_src_slot,
    output reg o_corr_src_rel,
    output reg [23:0] o_corr_rd_addr,
    output reg [6:0] o_corr_rd_len,
    output reg o_corr_rd_req,
    input wire i_corr_rd_gnt, i_corr_rd_vld,
    input wire [255:0] i_corr_rd_data,
    input wire i_corr_rd_last,
    output reg o_pix_vld,
    output reg [15:0] o_pix,
    output reg o_sop,o_eop,o_sof,o_eof,
    output reg [31:0] o_stat_frame_cnt,o_stat_line_loads,
    output reg [31:0] o_stat_line_hits,o_stat_pix_cnt,
    output reg [31:0] o_stat_seg_loads,
    output wire o_stat_line_stats_valid
);
    localparam BANKS=2*LINES_PER_SET;
    localparam [3:0] IDLE=0,HOLD=1,INIT_MAP=2,WAIT_INIT=3,
                     RUN=4,READ_REQ=5,READ_WAIT=6,SIM_RUN=7,
                     DRAIN=8,RELEASE=9,DONE=10,READ_ADDR=11;
    reg [3:0] state,read_return_state;
    reg [1:0] source_slot;
    reg signed [31:0] fx,fy,cx,cy,k1,k2,p1,p2;
    reg signed [31:0] a11,a12,a21,a22,tx,ty;
    reg aff_en;
    reg [10:0] gen_x,gen_y,consume_x,consume_y,out_x,out_y;
    reg gen_done, sample_phase, current_line_loaded;
    reg [10:0] gen_v;
    reg identity_mode,prefetch_active;
    reg [10:0] sim_x,sim_y,sim_a,sim_b;
    reg [10:0] load_row;
    reg [7:0] load_bank,replace_cursor;
    reg [26:0] coord_x [0:511],coord_y [0:511];
    reg [8:0] fifo_wr,fifo_rd;
    reg [9:0] fifo_count,inflight_count;
    reg [11:0] sample_wx,sample_wy,interp_wx,interp_wy;
    reg [2:0] sample_pipe;
    reg [11:0] align_wx,align_wy;
    reg [11:0] weight_x2,weight_y2;


    reg [31:0] coordinate_keys[0:511];
    reg [21:0] prepared_count,consumed_count,retired_count;
    // C28：独立预取指针 + 4 项弹性头队列。出队不再反馈到 512 深 RAM 地址。
    reg [8:0] head_fetch_ptr;
    reg [21:0] head_fetch_count,coord_produced_count;
    reg fetch_valid;
    reg [107:0] fetch_payload;
    reg [107:0] headq [0:3];
    reg [1:0] headq_wr,headq_rd;
    reg [2:0] headq_count;
    wire head_valid=(headq_count!=0);
    wire [107:0] head_payload=headq[headq_rd];
    wire [31:0] head_ids=head_payload[31:0];
    wire [26:0] head_x=head_payload[58:32];
    wire [26:0] head_y=head_payload[85:59];
    wire [10:0] head_row_a=head_payload[107:97];
    wire [10:0] head_row_b=head_payload[96:86];
    wire head_fetch_issue=SIM_MODE==0 && state!=IDLE && state!=HOLD &&
        state!=DRAIN && state!=RELEASE && state!=DONE &&
        head_fetch_count<coord_produced_count &&
        (identity_mode || head_fetch_count<prepared_count) &&
        ({1'b0,headq_count}+{3'd0,fetch_valid}<4);
    wire [31:0] fetch_key=coordinate_keys[head_fetch_ptr];

    // AB coordinate lookahead. Prepared IDs are pinned by absolute pixel sequence.
    // Data/tag retirement is delayed until both synchronous RAM reads finish.
    reg [31:0] prepared_ids[0:511];

    reg [8:0] prep_ptr;
    reg [8:0] prep_slot_q;
    reg [26:0] prep_x_q;
    reg [31:0] prep_key_q;

    reg [4:0] retire_pipe;
    reg [1:0] prep_state,seg_read_state;
    reg cached_key_valid;
    reg [31:0] cached_ids;
    reg [31:0] cached_key;
    wire [26:0] prep_x=prep_x_q;
    wire [31:0] prep_key=prep_key_q;
    wire [10:0] prep_a=prep_key[31:21],prep_b=prep_key[20:10];
    wire [4:0] prep_s0=prep_key[9:5],prep_s1=prep_key[4:0];
    wire [21:0] prep_distance=prepared_count-consumed_count;
    wire prep_available=state==RUN && !identity_mode &&
         prepared_count<32'd2073600 && {12'd0,fifo_count}>prep_distance && prep_distance<256;
    wire prep_next_ready=prepared_count<22'd2073599 &&
         coord_produced_count>prepared_count+22'd1 && prep_distance<255;
    wire [8:0] prep_next_ptr=prep_ptr+9'd1;
    wire [8:0] prep_read_ptr=(prep_state==0)?prep_ptr:prep_next_ptr;
    wire [26:0] prep_read_x=coord_x[prep_read_ptr];
    wire [31:0] prep_read_key=coordinate_keys[prep_read_ptr];
    wire prep_reuse=prep_available && prep_state==1 && cached_key_valid && prep_key==cached_key;
    wire lookup_busy,lookup_done,ids_ready,fetch_req;
    wire lookup_req=prep_available && prep_state==1 && !prep_reuse && !lookup_busy;
    wire [7:0] id_a0,id_a1,id_b0,id_b1,fetch_bank;
    wire prep_lookup_complete=prep_state==2 && lookup_done;
    wire prep_commit=prep_reuse || prep_lookup_complete;
    wire [31:0] prep_write_ids=prep_reuse ? cached_ids :
                                  {id_b1,id_b0,id_a1,id_a0};
    wire [10:0] fetch_row;
    wire [4:0] fetch_seg;
    reg touch_q;
    reg [31:0] touch_ids_q;
    reg [21:0] touch_seq_q;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            touch_q<=0;touch_ids_q<=0;touch_seq_q<=0;
        end else begin
            touch_q<=prep_reuse;
            if(prep_reuse)begin
                touch_ids_q<=cached_ids;
                touch_seq_q<=prepared_count;
            end
        end
    end
    wire seg_sample_dispatch=state==RUN && head_valid &&
         prepared_count!=consumed_count && ids_ready;
    wire sample_dispatch;
    wire seg_accept=!identity_mode && seg_read_state==1 && o_corr_rd_req && i_corr_rd_gnt;
    assign o_stat_line_stats_valid=identity_mode;

    reg start_valid_q;
    wire params_ok=
        i_fx>=32'sh00800000 && i_fy>=32'sh00800000 &&
        i_cx>=0 && i_cx<=32'sh077F0000 &&
        i_cy>=0 && i_cy<=32'sh04370000 &&
        i_k1>=-32'sd32768 && i_k1<=32'sd32768 &&
        i_k2>=-32'sd32768 && i_k2<=32'sd32768 &&
        i_p1>=-32'sd655 && i_p1<=32'sd655 &&
        i_p2>=-32'sd655 && i_p2<=32'sd655 &&
        i_aff_a11>=-32'sd131072 && i_aff_a11<=32'sd131072 &&
        i_aff_a12>=-32'sd131072 && i_aff_a12<=32'sd131072 &&
        i_aff_a21>=-32'sd131072 && i_aff_a21<=32'sd131072 &&
        i_aff_a22>=-32'sd131072 && i_aff_a22<=32'sd131072 &&
        i_aff_tx>=-32'sd268435456 && i_aff_tx<=32'sd268435456 &&
        i_aff_ty>=-32'sd268435456 && i_aff_ty<=32'sd268435456;

    wire map_init_done,map_valid;
    wire [26:0] map_sx,map_sy;
    wire [10:0] mapped_row_a=11'd1079-map_sy[26:16];
    wire [10:0] mapped_row_b=(map_sy[26:16]==11'd1079) ? 11'd0 :
                              11'd1078-map_sy[26:16];
    wire [10:0] mapped_x1=(map_sx[26:16]==11'd1919) ? 11'd1919 :
                           map_sx[26:16]+11'd1;
    wire map_issue=(state==RUN || state==READ_ADDR ||
                    state==READ_REQ || state==READ_WAIT) &&
                   !gen_done && ({1'b0,fifo_count}+{1'b0,inflight_count}<11'd480);
    undistort_map u_map(
        .clk(clk),.rst_n(rst_n),.i_frame_init(state==INIT_MAP),
        .i_fx(fx),.i_fy(fy),.i_cx(cx),.i_cy(cy),
        .i_k1(k1),.i_k2(k2),.i_p1(p1),.i_p2(p2),
        .i_aff_a11(a11),.i_aff_a12(a12),
        .i_aff_a21(a21),.i_aff_a22(a22),
        .i_aff_tx(tx),.i_aff_ty(ty),.i_aff_en(aff_en),
        .o_init_done(map_init_done),.i_valid(map_issue),
        .i_u(gen_x),.i_v(gen_v),
        .o_valid(map_valid),.o_sx_q16(map_sx),.o_sy_q16(map_sy)
    );

    wire [10:0] query_a=(SIM_MODE!=0)?sim_a:head_row_a;
    wire [10:0] query_b=(SIM_MODE!=0)?sim_b:head_row_b;
    wire hit_a,hit_b,prefetch_hit,load_done,load_error,sample_valid;
    wire [7:0] bank_a,bank_b;
    wire [15:0] p00,p01,p10,p11;
    wire line_sample_dispatch=(head_valid && (state==RUN ||
                           (prefetch_active && (state==READ_ADDR ||
                            state==READ_REQ || state==READ_WAIT))) &&
                          fifo_count!=0 &&
                          hit_a && hit_b);
    // C35：只暂停新取样；已发出的RAM/插值流水继续排空。
    // ready撤销后写FIFO保留至少32字，覆盖完整流水及Gamma延迟。
    assign sample_dispatch=(!USE_SINK_CREDIT || i_sink_ready) &&
                           (identity_mode?line_sample_dispatch:seg_sample_dispatch);
    wire cache_load_begin=identity_mode ? (state==READ_REQ && o_corr_rd_req && i_corr_rd_gnt) : seg_accept;
    undistort_cache_ab #(.LINES_PER_SET(LINES_PER_SET)) u_cache(
        .i_line_mode(identity_mode),
        .clk(clk),.rst_n(rst_n),.i_frame_clear(state==HOLD && i_corr_src_hold_gnt),
        .i_load_begin(cache_load_begin),
        .i_load_bank(identity_mode?load_bank:fetch_bank),.i_load_row(identity_mode?load_row:fetch_row),
        .i_load_vld(i_corr_rd_vld),.i_load_data(i_corr_rd_data),
        .i_load_last(i_corr_rd_last),.o_load_done(load_done),
        .o_load_error(load_error),
        .i_query_row_a(query_a),.i_query_row_b(query_b),
        .o_hit_a(hit_a),.o_hit_b(hit_b),
        .o_bank_a(bank_a),.o_bank_b(bank_b),
        .i_prefetch_row(consume_y+11'd1),.o_prefetch_hit(prefetch_hit),
        .i_sample_req(sample_dispatch),
        .i_sample_bank_a(identity_mode?bank_a:head_ids[7:0]),
        .i_sample_bank_b(identity_mode?bank_b:head_ids[23:16]),
        .i_sample_bank_a1(head_ids[15:8]),.i_sample_bank_b1(head_ids[31:24]),
        .i_sample_x(head_x[26:16]),.o_sample_valid(sample_valid),
        .o_p00(p00),.o_p01(p01),.o_p10(p10),.o_p11(p11),
        .i_lookup_req(lookup_req),.i_lookup_a(prep_a),.i_lookup_b(prep_b),
        .i_lookup_x(prep_x[26:16]),.i_lookup_seq(prepared_count),
        .o_lookup_busy(lookup_busy),.o_lookup_done(lookup_done),
        .o_id_a0(id_a0),.o_id_a1(id_a1),.o_id_b0(id_b0),.o_id_b1(id_b1),
        .i_touch(touch_q),.i_touch_ids(touch_ids_q),.i_touch_seq(touch_seq_q),
        .i_retired_count(retired_count),.i_ready_ids(head_ids),.o_ids_ready(ids_ready),
        .o_fetch_req(fetch_req),.o_fetch_bank(fetch_bank),.o_fetch_row(fetch_row),
        .o_fetch_seg(fetch_seg),.i_fetch_gnt(seg_accept)
    );
    wire interp_valid;
    wire [15:0] interp_pixel;
    undistort_bilinear u_bilinear(
        .clk(clk),.rst_n(rst_n),.i_valid(sample_valid),
        .i_p00(p00),.i_p01(p01),.i_p10(p10),.i_p11(p11),
        .i_wx(interp_wx),.i_wy(interp_wy),
        .o_valid(interp_valid),.o_pixel(interp_pixel)
    );

    function [7:0] next_bank;
        input [7:0] b;
        begin next_bank=(b==BANKS-1)?0:b+1'b1; end
    endfunction
    wire [7:0] victim=(hit_a && !hit_b && replace_cursor==bank_a) ?
                      next_bank(replace_cursor) :
                      ((!hit_a && hit_b && replace_cursor==bank_b) ?
                       next_bank(replace_cursor) : replace_cursor);
    reg [7:0] prefetch_victim;
    integer vi;
    always @* begin
        prefetch_victim=replace_cursor;
        for(vi=0;vi<BANKS;vi=vi+1)
            if(prefetch_victim==bank_a || prefetch_victim==bank_b)
                prefetch_victim=next_bank(prefetch_victim);
    end

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE;read_return_state<=IDLE;o_frame_busy<=0;
            o_corr_src_hold_req<=0;o_corr_src_rel<=0;
            o_corr_rd_addr<=0;o_corr_rd_len<=7'd119;o_corr_rd_req<=0;
            o_pix_vld<=0;o_pix<=0;o_sop<=0;o_eop<=0;o_sof<=0;o_eof<=0;
            o_stat_frame_cnt<=0;o_stat_seg_loads<=0;o_stat_line_loads<=0;
            o_stat_line_hits<=0;o_stat_pix_cnt<=0;
            source_slot<=0;gen_x<=0;gen_y<=0;gen_v<=11'd1079;consume_x<=0;consume_y<=0;
            out_x<=0;out_y<=0;gen_done<=0;sample_phase<=0;
            identity_mode<=0;prefetch_active<=0;
            current_line_loaded<=0;sim_x<=0;sim_y<=0;sim_a<=0;sim_b<=0;
            load_row<=0;load_bank<=0;replace_cursor<=0;
            fifo_wr<=0;fifo_rd<=0;fifo_count<=0;inflight_count<=0;
            sample_wx<=0;sample_wy<=0;interp_wx<=0;interp_wy<=0;
            sample_pipe<=0;align_wx<=0;align_wy<=0;weight_x2<=0;weight_y2<=0;
            fx<=0;fy<=0;cx<=0;cy<=0;k1<=0;k2<=0;p1<=0;p2<=0;
            prep_ptr<=0;prep_slot_q<=0;prep_x_q<=0;prep_key_q<=0;
            prepared_count<=0;consumed_count<=0;retired_count<=0;
            head_fetch_ptr<=0;head_fetch_count<=0;coord_produced_count<=0;fetch_valid<=0;fetch_payload<=0;headq_wr<=0;headq_rd<=0;headq_count<=0;
            retire_pipe<=0;prep_state<=0;seg_read_state<=0;cached_key_valid<=0;
            cached_ids<=0;cached_key<=0;
            a11<=0;a12<=0;a21<=0;a22<=0;tx<=0;ty<=0;aff_en<=0;
            start_valid_q<=0;
        end else begin
            start_valid_q<=state==IDLE && !start_valid_q && i_frame_start && params_ok;
            if(state==IDLE && !start_valid_q && i_frame_start)begin
                fx<=i_fx;fy<=i_fy;cx<=i_cx;cy<=i_cy;
                k1<=i_k1;k2<=i_k2;p1<=i_p1;p2<=i_p2;
                a11<=i_aff_a11;a12<=i_aff_a12;
                a21<=i_aff_a21;a22<=i_aff_a22;
                tx<=i_aff_tx;ty<=i_aff_ty;aff_en<=i_aff_en;
                identity_mode<=(SIM_MODE!=0) || i_k1==0 && i_k2==0 && i_p1==0 && i_p2==0 &&
                    (!i_aff_en || (i_aff_a11==32'sh00010000 &&
                    i_aff_a22==32'sh00010000 && i_aff_a12==0 &&
                    i_aff_a21==0 && i_aff_tx==0 && i_aff_ty==0));
            end
            o_corr_src_rel<=0;
            o_pix_vld<=0;o_sop<=0;o_eop<=0;o_sof<=0;o_eof<=0;
            sample_pipe<={sample_pipe[1:0],sample_dispatch};
            align_wx<=sample_wx;align_wy<=sample_wy;
            weight_x2<=align_wx;weight_y2<=align_wy;
            if(sample_pipe[2])begin
                interp_wx<=weight_x2;interp_wy<=weight_y2;
            end
            if(map_issue) begin
                if(gen_x==11'd1919) begin
                    gen_x<=0;
                    if(gen_y==11'd1079) gen_done<=1;
                    else begin gen_y<=gen_y+1'b1;gen_v<=gen_v-1'b1;end
                end else gen_x<=gen_x+1'b1;
            end
            if(map_valid && state!=IDLE) begin
                coordinate_keys[fifo_wr]<={mapped_row_a,mapped_row_b,1'b0,map_sx[26:23],1'b0,mapped_x1[10:7]};
                coord_produced_count<=coord_produced_count+1'b1;
                coord_x[fifo_wr]<=map_sx;
                coord_y[fifo_wr]<=map_sy;
                fifo_wr<=fifo_wr+1'b1;
            end
            if(sample_dispatch) fifo_rd<=fifo_rd+1'b1;
            case ({map_valid && state!=IDLE,sample_dispatch})
                2'b10: fifo_count<=fifo_count+1'b1;
                2'b01: fifo_count<=fifo_count-1'b1;
                default: ;
            endcase
            case ({map_issue,map_valid && state!=IDLE})
                2'b10: inflight_count<=inflight_count+1'b1;
                2'b01: inflight_count<=inflight_count-1'b1;
                default: ;
            endcase
            if(interp_valid && SIM_MODE==0) begin
                o_pix_vld<=1;o_pix<=interp_pixel;
                o_sop<=(out_x==0);o_eop<=(out_x==11'd1919);
                o_sof<=(out_y==0 && out_x==0);
                o_eof<=(out_y==11'd1079 && out_x==11'd1919);
                o_stat_pix_cnt<=o_stat_pix_cnt+1'b1;
                if(out_x==11'd1919) begin
                    out_x<=0;out_y<=out_y+1'b1;
                end else out_x<=out_x+1'b1;
            end
            if(sample_phase) sample_phase<=0;
            if(sample_dispatch) begin
                sample_phase<=1;
                sample_wx<=head_x[15:4];
                sample_wy<=head_y[15:4];
                if(consume_x==11'd1919) begin
                    if(identity_mode && !current_line_loaded)
                        o_stat_line_hits<=o_stat_line_hits+1'b1;
                    current_line_loaded<=0;
                    consume_x<=0;
                    if(consume_y==11'd1079) state<=DRAIN;
                    else consume_y<=consume_y+1'b1;
                end else consume_x<=consume_x+1'b1;
            end
            case(state)
                IDLE: if(start_valid_q) begin
                    o_frame_busy<=1;o_corr_src_hold_req<=1;
                    current_line_loaded<=0;source_slot<=0;
                    gen_x<=0;gen_y<=0;gen_v<=11'd1079;gen_done<=0;
                    consume_x<=0;consume_y<=0;out_x<=0;out_y<=0;
                    sim_x<=0;sim_y<=0;sim_a<=0;sim_b<=0;
                    fifo_wr<=0;fifo_rd<=0;fifo_count<=0;inflight_count<=0;
                    replace_cursor<=0;sample_phase<=0;sample_pipe<=0;
                    prefetch_active<=0;
                    prep_ptr<=0;prep_slot_q<=0;prep_x_q<=0;prep_key_q<=0;
                    prepared_count<=0;consumed_count<=0;retired_count<=0;
                    head_fetch_ptr<=0;head_fetch_count<=0;coord_produced_count<=0;fetch_valid<=0;fetch_payload<=0;headq_wr<=0;headq_rd<=0;headq_count<=0;
                    retire_pipe<=0;prep_state<=0;seg_read_state<=0;cached_key_valid<=0;
                    state<=HOLD;
                end
                HOLD: begin
                    // C42：参数检查只决定进入HOLD；统计清零本地完成，切断跨模块长CE路径。
                    o_stat_line_loads<=0;o_stat_seg_loads<=0;
                    o_stat_line_hits<=0;o_stat_pix_cnt<=0;
                    if(i_corr_src_hold_gnt) begin
                        source_slot<=i_corr_src_slot;
                        o_corr_src_hold_req<=0;
                        if(SIM_MODE!=0) state<=SIM_RUN;
                        else state<=INIT_MAP;
                    end
                end
                INIT_MAP: state<=WAIT_INIT;
                WAIT_INIT: if(map_init_done) state<=RUN;
                RUN: begin
                    if(identity_mode && consume_y<11'd1079 &&
                       consume_x>=11'd16 && consume_x<11'd1600 &&
                       head_valid && fifo_count!=0 && hit_a && hit_b && !prefetch_hit) begin
                        load_row<=consume_y+1'b1;
                        load_bank<=prefetch_victim;
                        prefetch_active<=1;
                        read_return_state<=RUN;state<=READ_ADDR;
                    end else if(identity_mode && head_valid && !sample_phase && fifo_count!=0) begin
                        if(!hit_a || !hit_b) begin
                            load_row<=hit_a?query_b:query_a;
                            load_bank<=victim;
                            prefetch_active<=0;
                            read_return_state<=RUN;state<=READ_ADDR;
                        end
                    end
                end
                SIM_RUN: begin
                    if(!hit_a || !hit_b) begin
                        load_row<=hit_a?query_b:query_a;
                        load_bank<=victim;
                        read_return_state<=SIM_RUN;state<=READ_ADDR;
                    end else if(sim_x==11'd1919) begin
                        if(!current_line_loaded)
                            o_stat_line_hits<=o_stat_line_hits+1'b1;
                        current_line_loaded<=0;sim_x<=0;
                        if(sim_y==11'd1079) state<=RELEASE;
                        else begin
                            sim_y<=sim_y+1'b1;
                            sim_a<=sim_y+1'b1;sim_b<=sim_y;
                        end
                    end else sim_x<=sim_x+1'b1;
                end
                READ_ADDR: begin
                    o_corr_rd_addr<=({22'd0,source_slot}<<20)+
                                     ({13'd0,load_row}*24'd960);
                    o_corr_rd_len<=7'd119;o_corr_rd_req<=1;
                    state<=READ_REQ;
                end
                READ_REQ: if(i_corr_rd_gnt) begin
                    o_corr_rd_req<=0;
                    o_stat_line_loads<=o_stat_line_loads+1'b1;
                    current_line_loaded<=1;
                    replace_cursor<=next_bank(load_bank);
                    state<=READ_WAIT;
                end
                READ_WAIT: if(load_done) begin
                    prefetch_active<=0;
                    state<=read_return_state;
                end
                DRAIN: if(o_stat_pix_cnt==32'd2073600) state<=RELEASE;
                RELEASE: begin
                    o_corr_src_rel<=1;
                    o_stat_frame_cnt<=o_stat_frame_cnt+1'b1;
                    state<=DONE;
                end
                DONE: begin o_frame_busy<=0;state<=IDLE;end
                default: state<=IDLE;
            endcase

            // 预取结果占用一个保留项，队列容量检查不依赖当前出队决定。
            // 大 RAM 读仅由寄存指针寻址；4:1 小队列承担每拍出队。
            if(state!=IDLE && state!=HOLD)begin
                fetch_valid<=head_fetch_issue;
                if(head_fetch_issue)begin
                    fetch_payload<={fetch_key[31:10],coord_y[head_fetch_ptr],
                                     coord_x[head_fetch_ptr],prepared_ids[head_fetch_ptr]};
                    head_fetch_ptr<=head_fetch_ptr+1'b1;
                    head_fetch_count<=head_fetch_count+1'b1;
                end
                if(fetch_valid)begin
                    headq[headq_wr]<=fetch_payload;
                    headq_wr<=headq_wr+1'b1;
                end
                if(sample_dispatch)headq_rd<=headq_rd+1'b1;
                case({fetch_valid,sample_dispatch})
                    2'b10:headq_count<=headq_count+1'b1;
                    2'b01:headq_count<=headq_count-1'b1;
                    default:;
                endcase
            end
            if(!identity_mode && state!=IDLE && state!=HOLD)begin
                retire_pipe<={retire_pipe[3:0],sample_dispatch};
                if(retire_pipe[4])retired_count<=retired_count+1'b1;
                if(sample_dispatch)consumed_count<=consumed_count+1'b1;
                if(prep_available && prep_state==0)begin
                    prep_slot_q<=prep_ptr;
                    prep_x_q<=prep_read_x;
                    prep_key_q<=prep_read_key;
                    prep_state<=1;
                end
                if(lookup_req)begin cached_key<=prep_key;prep_state<=2;end
                if(prep_lookup_complete)begin
                    cached_ids<={id_b1,id_b0,id_a1,id_a0};cached_key_valid<=1;
                end
                if(prep_commit)begin
                    prepared_ids[prep_slot_q]<=prep_write_ids;
                    prep_ptr<=prep_ptr+1'b1;prepared_count<=prepared_count+1'b1;
                    if(prep_next_ready)begin
                        prep_slot_q<=prep_next_ptr;
                        prep_x_q<=prep_read_x;
                        prep_key_q<=prep_read_key;
                        prep_state<=1;
                    end else prep_state<=0;
                end
                case(seg_read_state)
                    0:if(fetch_req)begin
                        o_corr_rd_addr<=({22'd0,source_slot}<<20)+
                                        ({13'd0,fetch_row}*24'd960)+({19'd0,fetch_seg}<<6);
                        o_corr_rd_len<=7'd7;o_corr_rd_req<=1;seg_read_state<=1;
                    end
                    1:if(i_corr_rd_gnt)begin
                        o_corr_rd_req<=0;o_stat_seg_loads<=o_stat_seg_loads+1'b1;
                        seg_read_state<=2;
                    end
                    2:if(load_done)seg_read_state<=0;
                    default:seg_read_state<=0;
                endcase
            end

        end
    end
endmodule
