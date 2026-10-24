// 单时钟域校正引擎；外部端口遵循任务书 V1.1。
module undistort_core #(
    parameter SIM_MODE = 0,
    parameter LINES_PER_SET = 2
)(
    input wire clk, rst_n,
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
    output reg [31:0] o_stat_line_hits,o_stat_pix_cnt
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
    reg identity_mode,prefetch_active;
    reg [10:0] sim_x,sim_y,sim_a,sim_b;
    reg [10:0] load_row;
    reg [7:0] load_bank,replace_cursor;
    reg [26:0] coord_x [0:31],coord_y [0:31];
    reg [4:0] fifo_wr,fifo_rd;
    reg [5:0] fifo_count,inflight_count;
    reg [11:0] sample_wx,sample_wy,interp_wx,interp_wy;
    reg [1:0] sample_pipe;

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
    wire map_issue=(state==RUN || state==READ_ADDR ||
                    state==READ_REQ || state==READ_WAIT) &&
                   !gen_done && ({1'b0,fifo_count}+{1'b0,inflight_count}<7'd16);
    undistort_map u_map(
        .clk(clk),.rst_n(rst_n),.i_frame_init(state==INIT_MAP),
        .i_fx(fx),.i_fy(fy),.i_cx(cx),.i_cy(cy),
        .i_k1(k1),.i_k2(k2),.i_p1(p1),.i_p2(p2),
        .i_aff_a11(a11),.i_aff_a12(a12),
        .i_aff_a21(a21),.i_aff_a22(a22),
        .i_aff_tx(tx),.i_aff_ty(ty),.i_aff_en(aff_en),
        .o_init_done(map_init_done),.i_valid(map_issue),
        .i_u(gen_x),.i_v(11'd1079-gen_y),
        .o_valid(map_valid),.o_sx_q16(map_sx),.o_sy_q16(map_sy)
    );

    wire [26:0] head_x=coord_x[fifo_rd],head_y=coord_y[fifo_rd];
    wire [10:0] head_row_a=11'd1079-head_y[26:16];
    wire [10:0] head_row_b=(head_y[26:16]==11'd1079) ?
                           11'd0 : 11'd1078-head_y[26:16];
    wire [10:0] query_a=(SIM_MODE!=0)?sim_a:head_row_a;
    wire [10:0] query_b=(SIM_MODE!=0)?sim_b:head_row_b;
    wire hit_a,hit_b,prefetch_hit,load_done,load_error,sample_valid;
    wire [7:0] bank_a,bank_b;
    wire [15:0] p00,p01,p10,p11;
    wire sample_dispatch=((state==RUN ||
                           (prefetch_active && (state==READ_ADDR ||
                            state==READ_REQ || state==READ_WAIT))) &&
                          !sample_phase && fifo_count!=0 &&
                          hit_a && hit_b);
    wire cache_load_begin=(state==READ_REQ && o_corr_rd_req && i_corr_rd_gnt);
    undistort_line_cache #(.LINES_PER_SET(LINES_PER_SET)) u_cache(
        .clk(clk),.rst_n(rst_n),.i_frame_clear(state==HOLD && i_corr_src_hold_gnt),
        .i_load_begin(cache_load_begin),
        .i_load_bank(load_bank),.i_load_row(load_row),
        .i_load_vld(i_corr_rd_vld),.i_load_data(i_corr_rd_data),
        .i_load_last(i_corr_rd_last),.o_load_done(load_done),
        .o_load_error(load_error),
        .i_query_row_a(query_a),.i_query_row_b(query_b),
        .o_hit_a(hit_a),.o_hit_b(hit_b),
        .o_bank_a(bank_a),.o_bank_b(bank_b),
        .i_prefetch_row(consume_y+11'd1),.o_prefetch_hit(prefetch_hit),
        .i_sample_req(sample_dispatch),
        .i_sample_bank_a(bank_a),.i_sample_bank_b(bank_b),
        .i_sample_x(head_x[26:16]),.o_sample_valid(sample_valid),
        .o_p00(p00),.o_p01(p01),.o_p10(p10),.o_p11(p11)
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
            o_stat_frame_cnt<=0;o_stat_line_loads<=0;
            o_stat_line_hits<=0;o_stat_pix_cnt<=0;
            source_slot<=0;gen_x<=0;gen_y<=0;consume_x<=0;consume_y<=0;
            out_x<=0;out_y<=0;gen_done<=0;sample_phase<=0;
            identity_mode<=0;prefetch_active<=0;
            current_line_loaded<=0;sim_x<=0;sim_y<=0;sim_a<=0;sim_b<=0;
            load_row<=0;load_bank<=0;replace_cursor<=0;
            fifo_wr<=0;fifo_rd<=0;fifo_count<=0;inflight_count<=0;
            sample_wx<=0;sample_wy<=0;interp_wx<=0;interp_wy<=0;
            sample_pipe<=0;
            fx<=0;fy<=0;cx<=0;cy<=0;k1<=0;k2<=0;p1<=0;p2<=0;
            a11<=0;a12<=0;a21<=0;a22<=0;tx<=0;ty<=0;aff_en<=0;
        end else begin
            o_corr_src_rel<=0;
            o_pix_vld<=0;o_sop<=0;o_eop<=0;o_sof<=0;o_eof<=0;
            sample_pipe<={sample_pipe[0],sample_dispatch};
            if(sample_pipe[1]) begin
                interp_wx<=sample_wx;
                interp_wy<=sample_wy;
            end
            if(map_issue) begin
                if(gen_x==11'd1919) begin
                    gen_x<=0;
                    if(gen_y==11'd1079) gen_done<=1;
                    else gen_y<=gen_y+1'b1;
                end else gen_x<=gen_x+1'b1;
            end
            if(map_valid && state!=IDLE) begin
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
                    if(!current_line_loaded)
                        o_stat_line_hits<=o_stat_line_hits+1'b1;
                    current_line_loaded<=0;
                    consume_x<=0;
                    if(consume_y==11'd1079) state<=DRAIN;
                    else consume_y<=consume_y+1'b1;
                end else consume_x<=consume_x+1'b1;
            end
            case(state)
                IDLE: if(i_frame_start && params_ok) begin
                    fx<=i_fx;fy<=i_fy;cx<=i_cx;cy<=i_cy;
                    k1<=i_k1;k2<=i_k2;p1<=i_p1;p2<=i_p2;
                    a11<=i_aff_a11;a12<=i_aff_a12;
                    a21<=i_aff_a21;a22<=i_aff_a22;
                    tx<=i_aff_tx;ty<=i_aff_ty;aff_en<=i_aff_en;
                    identity_mode<=i_k1==0 && i_k2==0 && i_p1==0 && i_p2==0 &&
                        (!i_aff_en || (i_aff_a11==32'sh00010000 &&
                        i_aff_a22==32'sh00010000 && i_aff_a12==0 &&
                        i_aff_a21==0 && i_aff_tx==0 && i_aff_ty==0));
                    o_frame_busy<=1;o_corr_src_hold_req<=1;
                    o_stat_line_loads<=0;o_stat_line_hits<=0;o_stat_pix_cnt<=0;
                    current_line_loaded<=0;source_slot<=0;
                    gen_x<=0;gen_y<=0;gen_done<=0;
                    consume_x<=0;consume_y<=0;out_x<=0;out_y<=0;
                    sim_x<=0;sim_y<=0;sim_a<=0;sim_b<=0;
                    fifo_wr<=0;fifo_rd<=0;fifo_count<=0;inflight_count<=0;
                    replace_cursor<=0;sample_phase<=0;sample_pipe<=0;
                    prefetch_active<=0;
                    state<=HOLD;
                end
                HOLD: if(i_corr_src_hold_gnt) begin
                    source_slot<=i_corr_src_slot;
                    o_corr_src_hold_req<=0;
                    if(SIM_MODE!=0) state<=SIM_RUN;
                    else state<=INIT_MAP;
                end
                INIT_MAP: state<=WAIT_INIT;
                WAIT_INIT: if(map_init_done) state<=RUN;
                RUN: begin
                    if(identity_mode && consume_y<11'd1079 &&
                       consume_x>=11'd16 && consume_x<11'd1600 &&
                       fifo_count!=0 && hit_a && hit_b && !prefetch_hit) begin
                        load_row<=consume_y+1'b1;
                        load_bank<=prefetch_victim;
                        prefetch_active<=1;
                        read_return_state<=RUN;state<=READ_ADDR;
                    end else if(!sample_phase && fifo_count!=0) begin
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
        end
    end
endmodule
