// C31: 128-pixel segments; len=7; no external port changes.
// C24 二号隔离试验：行列奇偶四存储体，取样 II=1；原 AB 源码保持不变。
// AB candidate: 2 parity memories x 384 x 256 bits = 24 KiB payload.
// Line mode uses 2 x 120 words per parity in the SAME memories.
// Segment mode: 96 fully associative 64px segments per parity; two-stage tags.
module undistort_cache_ab #(
    parameter LINES_PER_SET=2
)(
    input wire clk,rst_n,i_frame_clear,i_line_mode,
    input wire i_load_begin,
    input wire [7:0] i_load_bank,
    input wire [10:0] i_load_row,
    input wire i_load_vld,i_load_last,
    input wire [255:0] i_load_data,
    output reg o_load_done,o_load_error,
    input wire [10:0] i_query_row_a,i_query_row_b,i_prefetch_row,
    output reg o_hit_a,o_hit_b,o_prefetch_hit,
    output reg [7:0] o_bank_a,o_bank_b,
    input wire i_sample_req,
    input wire [7:0] i_sample_bank_a,i_sample_bank_b,
    input wire [7:0] i_sample_bank_a1,i_sample_bank_b1,
    input wire [10:0] i_sample_x,
    output reg o_sample_valid,
    output reg [15:0] o_p00,o_p01,o_p10,o_p11,
    input wire i_lookup_req,
    input wire [10:0] i_lookup_a,i_lookup_b,i_lookup_x,
    input wire [21:0] i_lookup_seq,
    output wire o_lookup_busy,
    output reg o_lookup_done,
    output reg [7:0] o_id_a0,o_id_a1,o_id_b0,o_id_b1,
    input wire i_touch,
    input wire [31:0] i_touch_ids,
    input wire [21:0] i_touch_seq,i_retired_count,
    input wire [31:0] i_ready_ids,
    output wire o_ids_ready,
    output wire o_fetch_req,
    output wire [7:0] o_fetch_bank,
    output wire [10:0] o_fetch_row,
    output wire [4:0] o_fetch_seg,
    input wire i_fetch_gnt
);
    generate if(LINES_PER_SET!=2)begin:unsupported_geometry
        AB_CACHE_REQUIRES_LINES_PER_SET_2 invalid_geometry();
    end endgenerate
    // Isolate tag/bank selection from physical RAM address decoding.  This
    // adds one cycle of latency while preserving one sample every two clocks.
    reg i_sample_req_q;
    reg [7:0] i_sample_bank_a_q,i_sample_bank_b_q,i_sample_bank_a1_q,i_sample_bank_b1_q;
    reg [10:0] i_sample_x_q;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            i_sample_req_q<=0;i_sample_bank_a_q<=0;i_sample_bank_b_q<=0;
            i_sample_bank_a1_q<=0;i_sample_bank_b1_q<=0;i_sample_x_q<=0;
        end else begin
            i_sample_req_q<=i_sample_req && !i_frame_clear;
            i_sample_bank_a_q<=i_sample_bank_a;i_sample_bank_b_q<=i_sample_bank_b;
            i_sample_bank_a1_q<=i_sample_bank_a1;i_sample_bank_b1_q<=i_sample_bank_b1;
            i_sample_x_q<=i_sample_x;
        end
    end
    // C29：数据接入级。metadata 在 grant 拍锁存，首数据允许同拍到达。
    // valid/last/data 同步延迟一拍，下一拍使用已锁存的写地址。
    reg load_vld_q,load_last_q;
    reg [255:0] load_data_q;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin load_vld_q<=0;load_last_q<=0;load_data_q<=0;end
        else begin
            load_vld_q<=i_load_vld && !i_frame_clear;
            load_last_q<=i_load_last;load_data_q<=i_load_data;
        end
    end
    // 每个 DDR 拍中的偶列/奇列各 8 像素，分别写入独立 128bit 存储体。
    reg [127:0] ram_ee[0:1023],ram_eo[0:1023];
    reg [127:0] ram_oe[0:1023],ram_oo[0:1023];
    reg [127:0] read_ee,read_eo,read_oe,read_oo;
    wire [127:0] write_even,write_odd;
    genvar wi;
    generate for(wi=0;wi<8;wi=wi+1)begin:split_columns
        assign write_even[wi*16+:16]=load_data_q[wi*32+:16];
        assign write_odd[wi*16+:16]=load_data_q[wi*32+16+:16];
    end endgenerate
    reg [3:0] line_valid;
    reg [10:0] line_row[0:3];
    reg [255:0] tag_valid,tag_ready,tag_pending;
    reg [10:0] tag_row[0:255];
    reg [4:0] tag_seg[0:255];
    // C26：保护窗口小于 262 像素；10bit 序号配合显式过期位，避免旧条目跨圈误判。
    // 每个退休序号逐拍经过；到 last_use+1 时清除 pin，更新/分配优先于清除。
    reg [9:0] last_use[0:255];
    reg [255:0] tag_pinned;
    reg [255:0] tag_recent;
    // C33：注册逐项保护使能，切断 qid 到所有 last_use CE 的布线关键路径。
    reg [255:0] protect_mask;
    reg [9:0] protect_seq;
    wire [9:0] expired_seq=i_retired_count[9:0]-10'd1;
    reg [7:0] fetch_fifo[0:255];
    reg [7:0] fetch_wr,fetch_rd;
    reg [8:0] fetch_count;
    reg load_active,load_line;
    reg [7:0] load_bank;
    reg [10:0] load_row;
    reg [6:0] load_beat;
    wire [6:0] last_beat=load_line?7'd119:7'd7;
    wire load_ok=load_active && load_vld_q && load_beat<=last_beat &&
                 (load_last_q==(load_beat==last_beat));
    wire [9:0] write_index=load_line ? ((load_bank[1]?9'd120:9'd0)+load_beat) :
                                      {load_bank[7:1],3'b000}+load_beat;
    wire write_parity=load_line?load_bank[0]:load_bank[0];
    assign o_fetch_bank=fetch_fifo[fetch_rd];
    assign o_fetch_row=tag_row[o_fetch_bank];
    assign o_fetch_seg=tag_seg[o_fetch_bank];
    assign o_fetch_req=!i_line_mode && fetch_count!=0 && !load_active;
    wire fetch_pop=o_fetch_req && i_fetch_gnt;
    assign o_ids_ready=tag_ready[i_ready_ids[7:0]] && tag_ready[i_ready_ids[15:8]] &&
                      tag_ready[i_ready_ids[23:16]] && tag_ready[i_ready_ids[31:24]];

    // 连续输入，每拍完成两行、两列的四点取样，接口输出延迟与原缓存相同。
    reg first_pending,output_pending;
    reg [2:0] lane0,lane1;
    reg parity_a,same_row,xpar0,xpar1;
    reg [15:0] stage_p00,stage_p01,stage_p10,stage_p11;
    wire [10:0] xn=(i_sample_x_q==1919)?11'd1919:i_sample_x_q+1'b1;
    wire [10:0] xe=i_sample_x_q[0]?xn:i_sample_x_q;
    wire [10:0] xo=i_sample_x_q[0]?i_sample_x_q:xn;
    wire [7:0] a1=i_line_mode?i_sample_bank_a_q:i_sample_bank_a1_q;
    wire [7:0] b1=i_line_mode?i_sample_bank_b_q:i_sample_bank_b1_q;
    wire [7:0] ae=i_sample_x_q[0]?a1:i_sample_bank_a_q;
    wire [7:0] ao=i_sample_x_q[0]?i_sample_bank_a_q:a1;
    wire [7:0] be=i_sample_x_q[0]?b1:i_sample_bank_b_q;
    wire [7:0] bo=i_sample_x_q[0]?i_sample_bank_b_q:b1;
    wire [9:0] addr_ae=i_line_mode?((ae[1]?9'd120:9'd0)+xe[10:4]):{ae[7:1],3'b000}+{7'd0,xe[6:4]};
    wire [9:0] addr_ao=i_line_mode?((ao[1]?9'd120:9'd0)+xo[10:4]):{ao[7:1],3'b000}+{7'd0,xo[6:4]};
    wire [9:0] addr_be=i_line_mode?((be[1]?9'd120:9'd0)+xe[10:4]):{be[7:1],3'b000}+{7'd0,xe[6:4]};
    wire [9:0] addr_bo=i_line_mode?((bo[1]?9'd120:9'd0)+xo[10:4]):{bo[7:1],3'b000}+{7'd0,xo[6:4]};
    wire [127:0] cur_ae=parity_a?read_oe:read_ee;
    wire [127:0] cur_ao=parity_a?read_oo:read_eo;
    wire [127:0] cur_be=same_row?cur_ae:(parity_a?read_ee:read_oe);
    wire [127:0] cur_bo=same_row?cur_ao:(parity_a?read_eo:read_oo);
    wire [127:0] cur_a0=xpar0?cur_ao:cur_ae;
    wire [127:0] cur_a1=xpar1?cur_ao:cur_ae;
    wire [127:0] cur_b0=xpar0?cur_bo:cur_be;
    wire [127:0] cur_b1=xpar1?cur_bo:cur_be;
    always @(posedge clk)begin
        if(load_ok && !write_parity)begin
            ram_ee[write_index]<=write_even;ram_eo[write_index]<=write_odd;
        end
        if(load_ok && write_parity)begin
            ram_oe[write_index]<=write_even;ram_oo[write_index]<=write_odd;
        end
        if(i_sample_req_q)begin
            read_ee<=ram_ee[i_sample_bank_a_q[0]?addr_be:addr_ae];
            read_eo<=ram_eo[i_sample_bank_a_q[0]?addr_bo:addr_ao];
            read_oe<=ram_oe[i_sample_bank_a_q[0]?addr_ae:addr_be];
            read_oo<=ram_oo[i_sample_bank_a_q[0]?addr_ao:addr_bo];
        end
    end

    // Four simultaneous keys, registered 8-entry groups, then registered select.
    localparam Q_IDLE=0,Q_MATCH=1,Q_SELECT=2,Q_CHECK=3,Q_VICTIM=4,Q_ALLOC=5,Q_DONE=6,
               Q_ELIG=7,Q_GROUP=8;
    // C38：两行共用列段比较器；跨128像素边界多一拍。
    reg compare_right;
    reg [3:0] qstate;
    reg [10:0] qa,qb;
    reg [4:0] qs0,qs1;
    reg [3:0] hash_a0,hash_a1,hash_b0,hash_b1;
    wire [4:0] lookup_s1=(i_lookup_x==1919)?5'd14:(i_lookup_x+11'd1)>>7;
    reg [10:0] miss_row_q;
    reg [4:0] miss_seg_q,miss_set_q;
    reg [21:0] qseq;
    reg [7:0] qid[0:3];
    reg [3:0] qfound;
    reg [1:0] qwhich;
    reg [7:0] match_hit[0:3];
    reg [7:0] match_id[0:31];
    // 替换策略：保留精确退休保护，按奇偶组分别轮转，不构建 96 路 22bit LRU 比较树。
    reg [2:0] victim_cursor[0:31];
    reg [7:0] eligible;
    reg [15:0] up_hit,any_hit;
    reg [7:0] up_id[0:15],any_id[0:15];
    reg [7:0] chosen;
    reg chosen_ok;
    assign o_lookup_busy=qstate!=Q_IDLE;
    wire [10:0] missing_row=qwhich[1]?qb:qa;
    wire [4:0] missing_seg=qwhich[0]?qs1:qs0;
    wire [3:0] missing_hash=missing_row[4:1]^missing_seg[3:0];
    wire [4:0] missing_set={missing_row[0],missing_hash};
    wire alloc=qstate==Q_ALLOC && chosen_ok;
    integer i,k,g,j,idx,sel,l;
    reg [10:0] cmp_row;
    reg [4:0] cmp_seg;
    reg [21:0] best_age;
    reg found;
    reg protected_id;
    reg cold_found;
    always @* begin
        o_hit_a=0;o_hit_b=0;o_prefetch_hit=0;o_bank_a=0;o_bank_b=0;
        for(l=0;l<4;l=l+1)begin
            if(line_valid[l] && line_row[l]==i_query_row_a)begin o_hit_a=1;o_bank_a=l;end
            if(line_valid[l] && line_row[l]==i_query_row_b)begin o_hit_b=1;o_bank_b=l;end
            if(line_valid[l] && line_row[l]==i_prefetch_row)o_prefetch_hit=1;
        end
    end
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            line_valid<=0;tag_valid<=0;tag_ready<=0;tag_pending<=0;tag_pinned<=0;tag_recent<=0;protect_mask<=0;protect_seq<=0;
            load_active<=0;load_line<=0;load_bank<=0;load_row<=0;load_beat<=0;
            o_load_done<=0;o_load_error<=0;fetch_wr<=0;fetch_rd<=0;fetch_count<=0;
            first_pending<=0;output_pending<=0;o_sample_valid<=0;
            lane0<=0;lane1<=0;parity_a<=0;same_row<=0;xpar0<=0;xpar1<=0;
            stage_p00<=0;stage_p01<=0;stage_p10<=0;stage_p11<=0;
            o_p00<=0;o_p01<=0;o_p10<=0;o_p11<=0;
            compare_right<=0;qstate<=Q_IDLE;qa<=0;qb<=0;qs0<=0;qs1<=0;qseq<=0;
            hash_a0<=0;hash_a1<=0;hash_b0<=0;hash_b1<=0;
            miss_row_q<=0;miss_seg_q<=0;miss_set_q<=0;
            qfound<=0;qwhich<=0;chosen<=0;chosen_ok<=0;for(i=0;i<32;i=i+1)victim_cursor[i]<=0;eligible<=0;up_hit<=0;any_hit<=0;
            o_lookup_done<=0;o_id_a0<=0;o_id_a1<=0;o_id_b0<=0;o_id_b1<=0;
        end else begin
            o_load_done<=0;o_load_error<=0;o_lookup_done<=0;protect_mask<=0;
            o_sample_valid<=0;first_pending<=i_sample_req_q;output_pending<=first_pending;
            if(i_sample_req_q)begin
                lane0<=i_sample_x_q[3:1];lane1<=xn[3:1];
                xpar0<=i_sample_x_q[0];xpar1<=xn[0];
                parity_a<=i_sample_bank_a_q[0];same_row<=i_sample_bank_a_q==i_sample_bank_b_q;
            end
            if(first_pending)begin
                stage_p00<=cur_a0[16*lane0+:16];stage_p10<=cur_b0[16*lane0+:16];
                stage_p01<=cur_a1[16*lane1+:16];stage_p11<=cur_b1[16*lane1+:16];
            end
            if(output_pending)begin
                o_p00<=stage_p00;o_p01<=stage_p01;o_p10<=stage_p10;o_p11<=stage_p11;
                o_sample_valid<=1;
            end
            if(i_frame_clear)begin
                line_valid<=0;tag_valid<=0;tag_ready<=0;tag_pending<=0;tag_pinned<=0;tag_recent<=0;protect_mask<=0;protect_seq<=0;
                fetch_wr<=0;fetch_rd<=0;fetch_count<=0;qstate<=Q_IDLE;for(i=0;i<32;i=i+1)victim_cursor[i]<=0;
                load_active<=0;first_pending<=0;output_pending<=0;
            end else begin
                for(i=0;i<256;i=i+1)
                    begin
                    if(tag_pinned[i] && last_use[i]==expired_seq)tag_pinned[i]<=0;
                    if(protect_mask[i])begin last_use[i]<=protect_seq;tag_pinned[i]<=1;tag_recent[i]<=1;end
                    end
                case({alloc,fetch_pop})
                    2'b10:fetch_count<=fetch_count+1'b1;
                    2'b01:fetch_count<=fetch_count-1'b1;
                    default:;
                endcase
                if(fetch_pop)fetch_rd<=fetch_rd+1'b1;
                if(i_load_begin)begin
                    if(load_active || i_load_row>1079 || (i_line_mode &&
                       (i_load_bank>3 || i_load_bank[0]!=i_load_row[0])))o_load_error<=1;
                    else begin
                        load_active<=1;load_line<=i_line_mode;
                        load_bank<=i_load_bank;load_row<=i_load_row;load_beat<=0;
                        if(i_line_mode)line_valid[i_load_bank]<=0;
                        // 段分配Q_ALLOC已清ready；grant时无需跨fetch FIFO再清一次。
                    end
                end
                if(load_active && load_vld_q)begin
                    if(!load_ok)begin
                        o_load_error<=1;load_active<=0;
                        if(load_line)line_valid[load_bank]<=0;
                        else begin tag_ready[load_bank]<=0;tag_pending[load_bank]<=0;end
                    end else if(load_last_q)begin
                        load_active<=0;o_load_done<=1;
                        if(load_line)begin line_row[load_bank]<=load_row;line_valid[load_bank]<=1;end
                        else begin tag_ready[load_bank]<=1;tag_pending[load_bank]<=0;end
                    end else load_beat<=load_beat+1'b1;
                end else if(load_vld_q && !load_active)o_load_error<=1;
                if(i_touch)begin
                    for(i=0;i<256;i=i+1)
                        protect_mask[i]<=i_touch_ids[7:0]==i || i_touch_ids[15:8]==i ||
                            i_touch_ids[23:16]==i || i_touch_ids[31:24]==i;
                    protect_seq<=i_touch_seq[9:0];
                end
                case(qstate)
                    Q_IDLE:if(i_lookup_req && !i_line_mode)begin
                        qa<=i_lookup_a;qb<=i_lookup_b;qs0<={1'b0,i_lookup_x[10:7]};
                        qs1<=lookup_s1;
                        hash_a0<=i_lookup_a[4:1]^i_lookup_x[10:7];
                        hash_a1<=i_lookup_a[4:1]^lookup_s1[3:0];
                        hash_b0<=i_lookup_b[4:1]^i_lookup_x[10:7];
                        hash_b1<=i_lookup_b[4:1]^lookup_s1[3:0];
                        qseq<=i_lookup_seq;compare_right<=0;qstate<=Q_MATCH;
                    end
                    Q_MATCH:begin
                        for(k=0;k<2;k=k+1)begin
                            cmp_row=k?qb:qa;cmp_seg=compare_right?qs1:qs0;
                            for(j=0;j<8;j=j+1)begin
                                idx={k?(compare_right?hash_b1:hash_b0):
                                       (compare_right?hash_a1:hash_a0),j[2:0],cmp_row[0]};
                                found=tag_valid[idx] && tag_row[idx]==cmp_row && tag_seg[idx]==cmp_seg;
                                if(!compare_right)begin
                                    match_hit[k*2][j]<=found;match_id[k*16+j]<=idx;
                                end
                                if(compare_right || qs0==qs1)begin
                                    match_hit[k*2+1][j]<=found;match_id[k*16+8+j]<=idx;
                                end
                            end
                        end
                        if(!compare_right && qs0!=qs1)compare_right<=1;
                        else qstate<=Q_SELECT;
                    end
                    Q_SELECT:begin
                        for(k=0;k<4;k=k+1)begin
                            found=0;sel=0;
                            for(g=0;g<8;g=g+1)if(match_hit[k][g])begin
                                found=1;sel=match_id[k*8+g];
                            end
                            qid[k]<=sel;qfound[k]<=found;
                        end
                        qwhich<=0;
                        // C35：四个键全部命中时，无需逐项再检查四拍。
                        if((|match_hit[0]) && (|match_hit[1]) &&
                           (|match_hit[2]) && (|match_hit[3]))qstate<=Q_DONE;
                        else qstate<=Q_CHECK;
                    end
                    Q_CHECK:begin
                        // Reuse duplicate neighbours allocated earlier in this batch.
                        found=qfound[qwhich];sel=qid[qwhich];
                        for(k=0;k<4;k=k+1)if(k<qwhich && qfound[k] &&
                            ((k>=2?qb:qa)==missing_row) && ((k%2?qs1:qs0)==missing_seg))
                            begin found=1;sel=qid[k];end
                        if(found)begin
                            qid[qwhich]<=sel;qfound[qwhich]<=1;
                            if(qwhich==3)qstate<=Q_DONE;else qwhich<=qwhich+1'b1;
                        end else begin
                            miss_row_q<=missing_row;
                            miss_seg_q<=missing_seg;
                            miss_set_q<=missing_set;
                            qstate<=Q_ELIG;
                        end
                    end
                    Q_ELIG:begin
                        for(j=0;j<8;j=j+1)begin
                            idx={miss_set_q[3:0],j[2:0],miss_set_q[4]};protected_id=0;
                            for(k=0;k<4;k=k+1)
                                if(qfound[k] && qid[k]==idx)protected_id=1;
                            eligible[j]<=!protected_id && (!tag_valid[idx] ||
                                (!tag_pending[idx] && !tag_pinned[idx]));
                        end
                        qstate<=Q_GROUP;
                    end
                    Q_GROUP:begin
                        // 优先选最近未用过的条目；一组全热时集体降温一轮。
                        cold_found=0;
                        for(j=0;j<8;j=j+1)begin
                            idx={miss_set_q[3:0],j[2:0],miss_set_q[4]};
                            if(eligible[j] && !tag_recent[idx])cold_found=1;
                        end
                        found=0;sel=0;
                        for(j=7;j>=0;j=j-1)begin
                            idx={miss_set_q[3:0],j[2:0],miss_set_q[4]};
                            if(eligible[j] && (!cold_found || !tag_recent[idx]))begin
                                found=1;sel=idx;
                            end
                        end
                        any_hit[0]<=found;any_id[0]<=sel;
                        found=0;sel=0;
                        for(j=7;j>=0;j=j-1)begin
                            idx={miss_set_q[3:0],j[2:0],miss_set_q[4]};
                            if(eligible[j] && j>=victim_cursor[miss_set_q] &&
                               (!cold_found || !tag_recent[idx]))begin
                                found=1;sel=idx;
                            end
                            if(!cold_found && eligible[j])tag_recent[idx]<=0;
                        end
                        up_hit[0]<=found;up_id[0]<=sel;qstate<=Q_VICTIM;
                    end
                    Q_VICTIM:begin
                        chosen<=up_hit[0]?up_id[0]:any_id[0];
                        chosen_ok<=up_hit[0] || any_hit[0];qstate<=Q_ALLOC;
                    end
                    Q_ALLOC:begin
                        if(chosen_ok)begin
                            victim_cursor[miss_set_q]<=chosen[3:1]+1'b1;
                            tag_valid[chosen]<=1;tag_ready[chosen]<=0;tag_pending[chosen]<=1;
                            tag_row[chosen]<=miss_row_q;tag_seg[chosen]<=miss_seg_q;
                            for(i=0;i<256;i=i+1)protect_mask[i]<=chosen==i;
                            protect_seq<=qseq[9:0];
                            fetch_fifo[fetch_wr]<=chosen;fetch_wr<=fetch_wr+1'b1;
                            qid[qwhich]<=chosen;qfound[qwhich]<=1;
                            if(qwhich==3)qstate<=Q_DONE;
                            else begin qwhich<=qwhich+1'b1;qstate<=Q_CHECK;end
                        end else qstate<=Q_CHECK;
                    end
                    Q_DONE:begin
                        o_id_a0<=qid[0];o_id_a1<=qid[1];o_id_b0<=qid[2];o_id_b1<=qid[3];
                        for(i=0;i<256;i=i+1)protect_mask[i]<=qid[0]==i || qid[1]==i || qid[2]==i || qid[3]==i;
                        protect_seq<=qseq[9:0];
                        o_lookup_done<=1;qstate<=Q_IDLE;
                    end
                    default:qstate<=Q_IDLE;
                endcase
            end
        end
    end
endmodule
