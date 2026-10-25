"""Incrementally derive candidate control from archived G4 (never edit G4)."""
from pathlib import Path
R=Path(__file__).resolve().parent
B=R.parent/'calibration_brown4_1080p30_20261022'


def replace_once(s,a,b):
    assert s.count(a)==1,(a,s.count(a))
    return s.replace(a,b)


def main():
    s=(R/'reference/undistort_core.v').read_text(encoding='utf-8-sig')
    s=replace_once(s,'parameter LINES_PER_SET = 2','parameter LINES_PER_SET = 2')
    s=replace_once(s,'output reg [31:0] o_stat_line_hits,o_stat_pix_cnt',
                  'output reg [31:0] o_stat_line_hits,o_stat_pix_cnt,\n    output reg [31:0] o_stat_seg_loads,\n    output wire o_stat_line_stats_valid')
    s=replace_once(s,'reg [26:0] coord_x [0:31],coord_y [0:31];','reg [26:0] coord_x [0:511],coord_y [0:511];')
    s=replace_once(s,'reg [4:0] fifo_wr,fifo_rd;','reg [8:0] fifo_wr,fifo_rd;')
    s=replace_once(s,'reg [5:0] fifo_count,inflight_count;','reg [9:0] fifo_count,inflight_count;')
    s=replace_once(s,'wire [26:0] head_x=coord_x[fifo_rd],head_y=coord_y[fifo_rd];',
                  '''reg head_valid;
    reg [26:0] head_x_reg,head_y_reg;
    reg [31:0] head_ids_reg;
    wire [26:0] head_x=head_x_reg,head_y=head_y_reg;''')
    s=replace_once(s,"({1'b0,fifo_count}+{1'b0,inflight_count}<7'd16)",
                  "({1'b0,fifo_count}+{1'b0,inflight_count}<11'd480)")
    s=replace_once(s,'wire sample_dispatch=((state==RUN ||',
                  'wire line_sample_dispatch=(head_valid && (state==RUN ||')
    s=replace_once(s,'wire cache_load_begin=(state==READ_REQ && o_corr_rd_req && i_corr_rd_gnt);',
                  'wire cache_load_begin=identity_mode ? (state==READ_REQ && o_corr_rd_req && i_corr_rd_gnt) : seg_accept;')
    s=replace_once(s,'undistort_line_cache #(.LINES_PER_SET(LINES_PER_SET)) u_cache(',
                  'undistort_cache_ab #(.LINES_PER_SET(LINES_PER_SET)) u_cache(\n        .i_line_mode(identity_mode),')
    s=replace_once(s,'.i_load_bank(load_bank),.i_load_row(load_row),',
                  '.i_load_bank(identity_mode?load_bank:fetch_bank),.i_load_row(identity_mode?load_row:fetch_row),')
    s=replace_once(s,'.i_sample_bank_a(bank_a),.i_sample_bank_b(bank_b),',
                  '.i_sample_bank_a(identity_mode?bank_a:head_ids[7:0]),\n        .i_sample_bank_b(identity_mode?bank_b:head_ids[23:16]),\n        .i_sample_bank_a1(head_ids[15:8]),.i_sample_bank_b1(head_ids[31:24]),')
    s=replace_once(s,'.o_p00(p00),.o_p01(p01),.o_p10(p10),.o_p11(p11)',
                  '''.o_p00(p00),.o_p01(p01),.o_p10(p10),.o_p11(p11),
        .i_lookup_req(lookup_req),.i_lookup_a(prep_a),.i_lookup_b(prep_b),
        .i_lookup_x(prep_x[26:16]),.i_lookup_seq(prepared_count),
        .o_lookup_busy(lookup_busy),.o_lookup_done(lookup_done),
        .o_id_a0(id_a0),.o_id_a1(id_a1),.o_id_b0(id_b0),.o_id_b1(id_b1),
        .i_touch(touch),.i_touch_ids(cached_ids),.i_touch_seq(prepared_count),
        .i_retired_count(retired_count),.i_ready_ids(head_ids),.o_ids_ready(ids_ready),
        .o_fetch_req(fetch_req),.o_fetch_bank(fetch_bank),.o_fetch_row(fetch_row),
        .o_fetch_seg(fetch_seg),.i_fetch_gnt(seg_accept)''')
    insert='''
    // AB coordinate lookahead. Prepared IDs are pinned by absolute pixel sequence.
    // Data/tag retirement is delayed until both synchronous RAM reads finish.
    reg [31:0] prepared_ids[0:511];
    reg [8:0] prep_ptr;
    reg [21:0] prepared_count,consumed_count,retired_count;
    reg [3:0] retire_pipe;
    reg [1:0] prep_state,seg_read_state;
    reg cached_key_valid;
    reg [31:0] cached_ids;
    reg [31:0] cached_key;
    wire [26:0] prep_x=coord_x[prep_ptr],prep_y=coord_y[prep_ptr];
    wire [10:0] prep_a=11'd1079-prep_y[26:16];
    wire [10:0] prep_b=prep_a==0?11'd0:prep_a-1'b1;
    wire [4:0] prep_s0=prep_x[26:22];
    wire [4:0] prep_s1=prep_x[26:16]==1919?5'd29:(prep_x[26:16]+11'd1)>>6;
    wire [31:0] prep_key={prep_a,prep_b,prep_s0,prep_s1};
    wire [21:0] prep_distance=prepared_count-consumed_count;
    wire prep_available=state==RUN && !identity_mode &&
         prepared_count<32'd2073600 && {12'd0,fifo_count}>prep_distance && prep_distance<256;
    wire prep_reuse=prep_available && prep_state==0 && cached_key_valid && prep_key==cached_key;
    wire lookup_req=prep_available && prep_state==0 && !prep_reuse && !lookup_busy;
    wire lookup_busy,lookup_done,ids_ready,fetch_req;
    wire [7:0] id_a0,id_a1,id_b0,id_b1,fetch_bank;
    wire [10:0] fetch_row;
    wire [4:0] fetch_seg;
    wire [31:0] head_ids=head_ids_reg;
    wire touch=prep_reuse;
    wire seg_sample_dispatch=state==RUN && head_valid && !sample_phase &&
         prepared_count!=consumed_count && ids_ready;
    wire sample_dispatch=identity_mode?line_sample_dispatch:seg_sample_dispatch;
    wire seg_accept=!identity_mode && seg_read_state==1 && o_corr_rd_req && i_corr_rd_gnt;
    assign o_stat_line_stats_valid=identity_mode;
'''
    s=replace_once(s,'    wire params_ok=',insert+'\n    wire params_ok=')
    s=replace_once(s,'if(!current_line_loaded)\n                        o_stat_line_hits',
                  'if(identity_mode && !current_line_loaded)\n                        o_stat_line_hits')
    # SIM_RUN remains an explicitly isolated legacy line-mode feature; the
    # segment functional path always uses SIM_MODE=0 and real map/bilinear.
    s=replace_once(s,'RUN: begin\n                    if(identity_mode',
                  'RUN: begin\n                    if(identity_mode')
    s=replace_once(s,'end else if(!sample_phase && fifo_count!=0) begin',
                  'end else if(identity_mode && head_valid && !sample_phase && fifo_count!=0) begin')
    s=replace_once(s,'fifo_count!=0 && hit_a && hit_b && !prefetch_hit',
                  'head_valid && fifo_count!=0 && hit_a && hit_b && !prefetch_hit')
    s=replace_once(s,'o_stat_frame_cnt<=0;o_stat_line_loads<=0;',
                  'o_stat_frame_cnt<=0;o_stat_seg_loads<=0;o_stat_line_loads<=0;')
    s=replace_once(s,'o_stat_line_loads<=0;o_stat_line_hits<=0;o_stat_pix_cnt<=0;',
                  'o_stat_line_loads<=0;o_stat_seg_loads<=0;o_stat_line_hits<=0;o_stat_pix_cnt<=0;')
    # Extra reset/init and independently operating single-transaction prefetch.
    s=replace_once(s,'prefetch_active<=0;\n                    state<=HOLD;',
                  '''prefetch_active<=0;
                    prep_ptr<=0;prepared_count<=0;consumed_count<=0;retired_count<=0;
                    head_valid<=0;head_x_reg<=0;head_y_reg<=0;head_ids_reg<=0;
                    retire_pipe<=0;prep_state<=0;seg_read_state<=0;cached_key_valid<=0;
                    state<=HOLD;''')
    s=replace_once(s,'fx<=0;fy<=0;cx<=0;cy<=0;k1<=0;k2<=0;p1<=0;p2<=0;',
                  '''fx<=0;fy<=0;cx<=0;cy<=0;k1<=0;k2<=0;p1<=0;p2<=0;
            prep_ptr<=0;prepared_count<=0;consumed_count<=0;retired_count<=0;
            head_valid<=0;head_x_reg<=0;head_y_reg<=0;head_ids_reg<=0;
            retire_pipe<=0;prep_state<=0;seg_read_state<=0;cached_key_valid<=0;
            cached_ids<=0;cached_key<=0;''')
    extra='''
            // Decouple the wide asynchronous coordinate/ID mux from tag lookup
            // and DRM addresses. Refill on the alternate II=2 sample cycle.
            if(sample_dispatch)head_valid<=0;
            else if(!head_valid && fifo_count!=0 &&
                    (identity_mode || prepared_count!=consumed_count))begin
                head_x_reg<=coord_x[fifo_rd];head_y_reg<=coord_y[fifo_rd];
                head_ids_reg<=prepared_ids[fifo_rd];head_valid<=1;
            end
            if(!identity_mode && state!=IDLE && state!=HOLD)begin
                retire_pipe<={retire_pipe[2:0],sample_dispatch};
                if(retire_pipe[3])retired_count<=retired_count+1'b1;
                if(sample_dispatch)consumed_count<=consumed_count+1'b1;
                if(prep_reuse)begin
                    prepared_ids[prep_ptr]<=cached_ids;
                    prep_ptr<=prep_ptr+1'b1;prepared_count<=prepared_count+1'b1;
                end
                if(lookup_req)begin cached_key<=prep_key;prep_state<=1;end
                if(prep_state==1 && lookup_done)begin
                    cached_ids<={id_b1,id_b0,id_a1,id_a0};cached_key_valid<=1;
                    prepared_ids[prep_ptr]<={id_b1,id_b0,id_a1,id_a0};
                    prep_ptr<=prep_ptr+1'b1;prepared_count<=prepared_count+1'b1;
                    prep_state<=0;
                end
                case(seg_read_state)
                    0:if(fetch_req)begin
                        o_corr_rd_addr<=({22'd0,source_slot}<<20)+
                                        ({13'd0,fetch_row}*24'd960)+({19'd0,fetch_seg}<<5);
                        o_corr_rd_len<=7'd3;o_corr_rd_req<=1;seg_read_state<=1;
                    end
                    1:if(i_corr_rd_gnt)begin
                        o_corr_rd_req<=0;o_stat_seg_loads<=o_stat_seg_loads+1'b1;
                        seg_read_state<=2;
                    end
                    2:if(load_done)seg_read_state<=0;
                    default:seg_read_state<=0;
                endcase
            end
'''
    s=replace_once(s,'                default: state<=IDLE;\n            endcase',
                  '                default: state<=IDLE;\n            endcase\n'+extra)
    s=replace_once(s,'identity_mode<=i_k1==0', 'identity_mode<=(SIM_MODE!=0) || i_k1==0')
    s=replace_once(s,'reg [1:0] sample_pipe;','reg [2:0] sample_pipe;')
    s=replace_once(s,'sample_pipe<={sample_pipe[0],sample_dispatch};',
                      'sample_pipe<={sample_pipe[1:0],sample_dispatch};')
    s=replace_once(s,'if(sample_pipe[1]) begin','if(sample_pipe[2]) begin')
    s=replace_once(s,'reg [2:0] sample_pipe;',
                  'reg [2:0] sample_pipe;\n    reg [11:0] align_wx,align_wy;')
    s=replace_once(s,'sample_pipe<=0;\n            fx<=0;',
                  'sample_pipe<=0;align_wx<=0;align_wy<=0;\n            fx<=0;')
    s=replace_once(s,'sample_pipe<={sample_pipe[1:0],sample_dispatch};',
                  'sample_pipe<={sample_pipe[1:0],sample_dispatch};\n            align_wx<=sample_wx;align_wy<=sample_wy;')
    s=replace_once(s,'interp_wx<=sample_wx;', 'interp_wx<=align_wx;')
    s=replace_once(s,'interp_wy<=sample_wy;', 'interp_wy<=align_wy;')
    s=replace_once(s,'wire [10:0] head_row_a=11\'d1079-head_y[26:16];',
                  'reg [10:0] head_row_a_reg,head_row_b_reg;\n    wire [26:0] fifo_head_y=coord_y[fifo_rd];\n    wire [10:0] head_row_a=head_row_a_reg;')
    s=replace_once(s,"wire [10:0] head_row_b=(head_y[26:16]==11'd1079) ?\n                           11'd0 : 11'd1078-head_y[26:16];",
                  'wire [10:0] head_row_b=head_row_b_reg;')
    s=s.replace('head_valid<=0;head_x_reg<=0;',
                'head_row_a_reg<=0;head_row_b_reg<=0;head_valid<=0;head_x_reg<=0;')
    s=replace_once(s,'head_x_reg<=coord_x[fifo_rd];head_y_reg<=coord_y[fifo_rd];',
                  """head_x_reg<=coord_x[fifo_rd];head_y_reg<=coord_y[fifo_rd];
                head_row_a_reg<=11'd1079-fifo_head_y[26:16];
                head_row_b_reg<=(fifo_head_y[26:16]==11'd1079) ? 11'd0 :
                                11'd1078-fifo_head_y[26:16];""")
    # Precompute row/segment keys at map insertion, so the preparation pointer
    # does not drive an async FIFO -> subtract -> equality -> RAM write path.
    s=replace_once(s,'reg [31:0] prepared_ids[0:511];',
                  'reg [31:0] prepared_ids[0:511];\n    reg [31:0] coordinate_keys[0:511];')
    s=replace_once(s,"wire [10:0] prep_a=11'd1079-prep_y[26:16];\n    wire [10:0] prep_b=prep_a==0?11'd0:prep_a-1'b1;\n    wire [4:0] prep_s0=prep_x[26:22];\n    wire [4:0] prep_s1=prep_x[26:16]==1919?5'd29:(prep_x[26:16]+11'd1)>>6;\n    wire [31:0] prep_key={prep_a,prep_b,prep_s0,prep_s1};",
                  '''wire [31:0] prep_key=coordinate_keys[prep_ptr];
    wire [10:0] prep_a=prep_key[31:21],prep_b=prep_key[20:10];
    wire [4:0] prep_s0=prep_key[9:5],prep_s1=prep_key[4:0];''')
    s=replace_once(s,'wire [26:0] map_sx,map_sy;',
                  """wire [26:0] map_sx,map_sy;
    wire [10:0] mapped_row_a=11'd1079-map_sy[26:16];
    wire [10:0] mapped_row_b=(map_sy[26:16]==11'd1079) ? 11'd0 :
                              11'd1078-map_sy[26:16];
    wire [10:0] mapped_x1=(map_sx[26:16]==11'd1919) ? 11'd1919 :
                           map_sx[26:16]+11'd1;""")
    s=replace_once(s,'coord_x[fifo_wr]<=map_sx;',
                  '''coordinate_keys[fifo_wr]<={mapped_row_a,mapped_row_b,map_sx[26:22],mapped_x1[10:6]};
                coord_x[fifo_wr]<=map_sx;''')
    # Count the frozen top-down map row directly alongside gen_y. This removes
    # a subtraction on the affine DSP input without changing map arithmetic.
    s=replace_once(s,'reg gen_done, sample_phase, current_line_loaded;',
                  'reg gen_done, sample_phase, current_line_loaded;\n    reg [10:0] gen_v;')
    s=s.replace(".i_v(11'd1079-gen_y)",'.i_v(gen_v)')
    s=s.replace('source_slot<=0;gen_x<=0;gen_y<=0;',
                "source_slot<=0;gen_x<=0;gen_y<=0;gen_v<=11'd1079;")
    s=s.replace('gen_x<=0;gen_y<=0;gen_done<=0;',
                "gen_x<=0;gen_y<=0;gen_v<=11'd1079;gen_done<=0;")
    s=replace_once(s,"else gen_y<=gen_y+1'b1;",
                  "else begin gen_y<=gen_y+1'b1;gen_v<=gen_v-1'b1;end")
    s=s.replace('reg [3:0] retire_pipe;', 'reg [4:0] retire_pipe;')
    s=s.replace('retire_pipe[2:0],sample_dispatch','retire_pipe[3:0],sample_dispatch')
    s=s.replace('if(retire_pipe[3])','if(retire_pipe[4])')
    # R1: declaration initializers are continuous assignments, but ModelSim
    # 10.7 resolves their RHS immediately. Declare dependencies before use.
    s=replace_once(s,'    reg head_valid;\n','')
    s=replace_once(s,'    reg [31:0] head_ids_reg;\n','')
    s=replace_once(s,'    // AB coordinate lookahead.',
                  '    reg head_valid;\n    reg [31:0] head_ids_reg;\n\n    // AB coordinate lookahead.')
    s=replace_once(s,'    wire lookup_busy,lookup_done,ids_ready,fetch_req;\n','')
    s=replace_once(s,'    wire lookup_req=',
                  '    wire lookup_busy,lookup_done,ids_ready,fetch_req;\n    wire lookup_req=')
    s=replace_once(s,'    wire sample_dispatch=identity_mode?line_sample_dispatch:seg_sample_dispatch;',
                  '    wire sample_dispatch;')
    s=replace_once(s,'    wire cache_load_begin=',
                  '    assign sample_dispatch=identity_mode?line_sample_dispatch:seg_sample_dispatch;\n    wire cache_load_begin=')
    (R/'source/rtl/undistort_core.v').write_text(s,encoding='utf-8')
    tb=(R/'reference/undistort_line_cache_tb.v').read_text(encoding='utf-8-sig')
    tb=tb.replace('undistort_line_cache dut(','''undistort_cache_ab dut(
        .i_line_mode(1'b1),.i_sample_bank_a1(8'd0),.i_sample_bank_b1(8'd0),
        .i_lookup_req(1'b0),.i_lookup_a(11'd0),.i_lookup_b(11'd0),.i_lookup_x(11'd0),
        .i_lookup_seq(22'd0),.i_touch(1'b0),.i_touch_ids(32'd0),
        .i_touch_seq(22'd0),.i_retired_count(22'd0),.i_ready_ids(32'd0),.i_fetch_gnt(1'b0),''')
    # SV reserves "packed"; keep this purely lexical change in the equivalent TB.
    import re
    tb=re.sub(r'\bpacked\b','packed_data',tb)
    (R/'sim/cache72_ab_tb.v').write_text(tb,encoding='utf-8')
    print('CANDIDATE_SOURCES GENERATED; G4 inputs untouched')


if __name__=='__main__': main()
