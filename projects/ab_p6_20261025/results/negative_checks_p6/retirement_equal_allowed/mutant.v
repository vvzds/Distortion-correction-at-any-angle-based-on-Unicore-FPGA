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
    reg [255:0] ram_even[0:383],ram_odd[0:383];
    reg [255:0] read_even,read_odd;
    reg [3:0] line_valid;
    reg [10:0] line_row[0:3];
    reg [191:0] tag_valid,tag_ready,tag_pending;
    reg [10:0] tag_row[0:191];
    reg [4:0] tag_seg[0:191];
    wire [21:0] last_use[0:191];
    reg [7:0] fetch_fifo[0:255];
    reg [7:0] fetch_wr,fetch_rd;
    reg [8:0] fetch_count;
    reg load_active,load_line;
    reg [7:0] load_bank;
    reg [10:0] load_row;
    reg [6:0] load_beat;
    wire [6:0] last_beat=load_line?7'd119:7'd3;
    wire load_ok=load_active && i_load_vld && load_beat<=last_beat &&
                 (i_load_last==(load_beat==last_beat));
    wire [8:0] write_index=load_line ? ((load_bank[1]?9'd120:9'd0)+load_beat) :
                                      {load_bank[7:1],2'b00}+load_beat;
    wire write_parity=load_line?load_bank[0]:load_bank[0];
    assign o_fetch_bank=fetch_fifo[fetch_rd];
    assign o_fetch_row=tag_row[o_fetch_bank];
    assign o_fetch_seg=tag_seg[o_fetch_bank];
    assign o_fetch_req=!i_line_mode && fetch_count!=0 && !load_active;
    wire fetch_pop=o_fetch_req && i_fetch_gnt;
    assign o_ids_ready=tag_ready[i_ready_ids[7:0]] && tag_ready[i_ready_ids[15:8]] &&
                      tag_ready[i_ready_ids[23:16]] && tag_ready[i_ready_ids[31:24]];

    // Data port: successive x/x+1 reads, one synchronous read per parity RAM.
    reg first_pending,output_pending;
    reg [7:0] saved_a1,saved_b1;
    reg [10:0] saved_next;
    reg [3:0] lane0,lane1;
    reg parity_a;
    reg [255:0] first_a,first_b;
    wire [10:0] xn=(i_sample_x_q==1919)?11'd1919:i_sample_x_q+1'b1;
    wire [7:0] use_a=i_sample_req_q?i_sample_bank_a_q:saved_a1;
    wire [7:0] use_b=i_sample_req_q?i_sample_bank_b_q:saved_b1;
    wire [10:0] use_x=i_sample_req_q?i_sample_x_q:saved_next;
    wire [8:0] addr_a=i_line_mode ? ((use_a[1]?9'd120:9'd0)+use_x[10:4]) :
                                    {use_a[7:1],2'b00}+{7'd0,use_x[5:4]};
    wire [8:0] addr_b=i_line_mode ? ((use_b[1]?9'd120:9'd0)+use_x[10:4]) :
                                    {use_b[7:1],2'b00}+{7'd0,use_x[5:4]};
    wire read_enable=i_sample_req_q || first_pending;
    wire [8:0] even_addr=use_a[0]?addr_b:addr_a;
    wire [8:0] odd_addr=use_a[0]?addr_a:addr_b;
    wire [255:0] current_a=parity_a?read_odd:read_even;
    // Adjacent source rows have opposite parity, except rowB=rowA=0.
    reg same_row;
    wire [255:0] current_b=same_row?current_a:(parity_a?read_even:read_odd);
    always @(posedge clk) begin
        if(load_ok && !write_parity)ram_even[write_index]<=i_load_data;
        if(load_ok && write_parity)ram_odd[write_index]<=i_load_data;
        if(read_enable)begin
            read_even<=ram_even[even_addr];read_odd<=ram_odd[odd_addr];
        end
    end

    // Four simultaneous keys, registered 8-entry groups, then registered select.
    localparam Q_IDLE=0,Q_MATCH=1,Q_SELECT=2,Q_CHECK=3,Q_VICTIM=4,Q_ALLOC=5,Q_DONE=6,
               Q_ELIG=7,Q_GROUP=8;
    reg [3:0] qstate;
    reg [10:0] qa,qb;
    reg [4:0] qs0,qs1;
    reg [21:0] qseq;
    reg [7:0] qid[0:3];
    // IDs resolved in this lookup; used only for Q_DONE timestamp updates.
    wire [191:0] done_mask;
    // P4: compare stable lookup keys in an existing stage.
    reg lookup_same_row,lookup_same_seg;
    reg [3:0] qfound;
    reg [1:0] qwhich;
    reg [11:0] match_hit[0:3];
    reg [7:0] match_id[0:47];
    wire [11:0] victim_hit;
    wire [7:0] victim_id[0:11];
    wire [21:0] victim_age[0:11];
    wire [30:0] victim_leaf[0:95];
    reg [30:0] tree[0:15];
    // Balanced priority tree. Bit30=eligible, bits29:8=age, bits7:0=ID.
    function [30:0] older;
        input [30:0] a,b;
        begin
            if(!a[30])older=b;
            else if(!b[30])older=a;
            else older=(a[29:8]<b[29:8])?a:b;
        end
    endfunction
    reg [7:0] chosen;
    reg chosen_ok;
    assign o_lookup_busy=qstate!=Q_IDLE;
    wire [10:0] missing_row=qwhich[1]?qb:qa;
    wire [4:0] missing_seg=qwhich[0]?qs1:qs0;
    wire alloc=qstate==Q_ALLOC && chosen_ok;
    // Tag arrays and writes stay in the original process to preserve RAM inference.
    reg local_check_found;
    reg [7:0] local_check_id;
    always @* begin
        local_check_found=1'bx;local_check_id=8'hxx;
                        case(qwhich)
                            0:begin local_check_found=qfound[0];local_check_id=qid[0];end
                            1:begin
                                if(qfound[0] && lookup_same_seg)begin local_check_found=1;local_check_id=qid[0];end
                                else begin local_check_found=qfound[1];local_check_id=qid[1];end
                            end
                            2:begin
                                if(qfound[1] && lookup_same_row && lookup_same_seg)begin local_check_found=1;local_check_id=qid[1];end
                                else if(qfound[0] && lookup_same_row)begin local_check_found=1;local_check_id=qid[0];end
                                else begin local_check_found=qfound[2];local_check_id=qid[2];end
                            end
                            3:begin
                                if(qfound[2] && lookup_same_seg)begin local_check_found=1;local_check_id=qid[2];end
                                else if(qfound[1] && lookup_same_row)begin local_check_found=1;local_check_id=qid[1];end
                                else if(qfound[0] && lookup_same_row && lookup_same_seg)begin local_check_found=1;local_check_id=qid[0];end
                                else begin local_check_found=qfound[3];local_check_id=qid[3];end
                            end
                        endcase
    end
    genvar local_g,local_j;
    generate for(local_g=0;local_g<12;local_g=local_g+1)begin:local_group
        wire [351:0] group_ages;
        wire [15:0] group_mask;
        wire [247:0] group_leaf;
        wire [30:0] group_winner;
        // P6R1: a lexical local block preserves all 22 bits while allowing
        // the existing host's constant sequence MSB to propagate in synthesis.
        begin:u_age_victim
            localparam integer GROUP=local_g;
            wire i_select=qstate==Q_SELECT;
            wire i_mark=qstate==Q_CHECK && local_check_found;
            wire [7:0] i_mark_id=local_check_id;
            wire i_alloc=alloc;
            wire [7:0] i_alloc_id=chosen;
            wire i_commit=qstate==Q_DONE;
            wire [21:0] i_seq=qseq;
            wire i_elig=qstate==Q_ELIG;
            wire i_group=qstate==Q_GROUP;
            wire i_parity=missing_row[0];
            wire [15:0] i_tag_valid=tag_valid[16*local_g+:16];
            wire [15:0] i_tag_pending=tag_pending[16*local_g+:16];
            wire [3:0] i_qfound=qfound;
            wire [31:0] i_qids={qid[3],qid[2],qid[1],qid[0]};
            wire [351:0] o_ages;
            assign group_ages=o_ages;
            wire [15:0] o_mask;
            assign group_mask=o_mask;
            wire [247:0] o_leaf;
            assign group_leaf=o_leaf;
            wire [30:0] o_winner;
            assign group_winner=o_winner;
    reg [21:0] age[0:15];reg [15:0] mask;
    reg [30:0] leaf[0:7];reg [30:0] winner;
    wire bank_alloc=i_alloc && i_alloc_id[7:4]==GROUP;
    wire bank_mark=i_mark && i_mark_id[7:4]==GROUP;
    wire touch0=i_touch && i_touch_ids[7:4]==GROUP;
    wire touch1=i_touch && i_touch_ids[15:12]==GROUP;
    wire touch2=i_touch && i_touch_ids[23:20]==GROUP;
    wire touch3=i_touch && i_touch_ids[31:28]==GROUP;
    assign o_mask=mask;assign o_winner=winner;
    genvar view;
    for(view=0;view<16;view=view+1)begin:age_output
        assign o_ages[22*view+:22]=age[view];
    end
    for(view=0;view<8;view=view+1)begin:leaf_output
        assign o_leaf[31*view+:31]=leaf[view];
    end
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)mask<=0;
        else if(i_frame_clear)mask<=0;
        else if(i_select)mask<=0;
        else if(bank_mark)mask[i_mark_id[3:0]]<=1'b1;
        else if(bank_alloc)mask[i_alloc_id[3:0]]<=1'b1;
    end
    integer s;
    // Same old-value semantics and priority. No reset/clear value is introduced.
    always @(posedge clk)begin
        if(!rst_n)begin end
        else if(i_frame_clear)begin end
        else for(s=0;s<16;s=s+1)begin
            if((bank_alloc && i_alloc_id[3:0]==s) || (i_commit && mask[s]))age[s]<=i_seq;
            else if((touch0 && i_touch_ids[3:0]==s) || (touch1 && i_touch_ids[11:8]==s) ||
                    (touch2 && i_touch_ids[19:16]==s) || (touch3 && i_touch_ids[27:24]==s))age[s]<=i_touch_seq;
        end
    end
    function [30:0] local_older;
        input [30:0] a,b;
        begin
            if(!a[30])local_older=b;
            else if(!b[30])local_older=a;
            else local_older=(a[29:8]<b[29:8])?a:b;
        end
    endfunction
    integer j,k,local_idx,gid;
    reg protected_id;
    reg [30:0] tree[0:15];
    always @(posedge clk)begin
        if(!rst_n)begin end
        else if(i_frame_clear)begin end
        else begin
            if(i_elig)begin
                for(j=0;j<8;j=j+1)begin
                    local_idx=2*j+i_parity;gid=16*GROUP+local_idx;protected_id=0;
                    for(k=0;k<4;k=k+1)
                        if(i_qfound[k] && i_qids[k*8+:8]==gid)protected_id=1;
                    leaf[j]<={(!protected_id && (!i_tag_valid[local_idx] ||
                        (!i_tag_pending[local_idx] && age[local_idx]<=i_retired_count))),
                        (i_tag_valid[local_idx]?age[local_idx]:22'd0),gid[7:0]};
                end
            end
            if(i_group)begin
                for(j=0;j<8;j=j+1)tree[8+j]=leaf[j];
                for(j=7;j>0;j=j-1)tree[j]=local_older(tree[j*2],tree[j*2+1]);
                winner<=tree[1];
            end
        end
    end
        end

        assign victim_hit[local_g]=group_winner[30];
        assign victim_age[local_g]=group_winner[29:8];assign victim_id[local_g]=group_winner[7:0];
        for(local_j=0;local_j<16;local_j=local_j+1)begin:age_view
            assign last_use[16*local_g+local_j]=group_ages[22*local_j+:22];
            assign done_mask[16*local_g+local_j]=group_mask[local_j];
        end
        for(local_j=0;local_j<8;local_j=local_j+1)begin:leaf_view
            assign victim_leaf[8*local_g+local_j]=group_leaf[31*local_j+:31];
        end
    end endgenerate
    integer i,k,g,j,idx,sel,l;
    reg [10:0] cmp_row;
    reg [4:0] cmp_seg;
    reg [21:0] best_age;
    reg found;
    reg protected_id;
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
            line_valid<=0;tag_valid<=0;tag_ready<=0;tag_pending<=0;
            load_active<=0;load_line<=0;load_bank<=0;load_row<=0;load_beat<=0;
            o_load_done<=0;o_load_error<=0;fetch_wr<=0;fetch_rd<=0;fetch_count<=0;
            first_pending<=0;output_pending<=0;o_sample_valid<=0;
            saved_a1<=0;saved_b1<=0;saved_next<=0;lane0<=0;lane1<=0;
            parity_a<=0;same_row<=0;first_a<=0;first_b<=0;
            o_p00<=0;o_p01<=0;o_p10<=0;o_p11<=0;
            qstate<=Q_IDLE;qa<=0;qb<=0;qs0<=0;qs1<=0;qseq<=0;
            qfound<=0;qwhich<=0;chosen<=0;chosen_ok<=0;
            lookup_same_row<=0;lookup_same_seg<=0;
            o_lookup_done<=0;o_id_a0<=0;o_id_a1<=0;o_id_b0<=0;o_id_b1<=0;
        end else begin
            o_load_done<=0;o_load_error<=0;o_lookup_done<=0;
            o_sample_valid<=0;first_pending<=i_sample_req_q;output_pending<=first_pending;
            if(i_sample_req_q)begin
                saved_a1<=i_line_mode?i_sample_bank_a_q:i_sample_bank_a1_q;
                saved_b1<=i_line_mode?i_sample_bank_b_q:i_sample_bank_b1_q;
                saved_next<=xn;lane0<=i_sample_x_q[3:0];lane1<=xn[3:0];
                parity_a<=i_sample_bank_a_q[0];same_row<=i_sample_bank_a_q==i_sample_bank_b_q;
            end
            if(first_pending)begin first_a<=current_a;first_b<=current_b;end
            if(output_pending)begin
                o_p00<=first_a[16*lane0+:16];o_p10<=first_b[16*lane0+:16];
                o_p01<=current_a[16*lane1+:16];o_p11<=current_b[16*lane1+:16];
                o_sample_valid<=1;
            end
            if(i_frame_clear)begin
                line_valid<=0;tag_valid<=0;tag_ready<=0;tag_pending<=0;
                fetch_wr<=0;fetch_rd<=0;fetch_count<=0;qstate<=Q_IDLE;
                load_active<=0;first_pending<=0;output_pending<=0;
            end else begin
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
                        else tag_ready[i_load_bank]<=0;
                    end
                end
                if(load_active && i_load_vld)begin
                    if(!load_ok)begin
                        o_load_error<=1;load_active<=0;
                        if(load_line)line_valid[load_bank]<=0;
                        else begin tag_ready[load_bank]<=0;tag_pending[load_bank]<=0;end
                    end else if(i_load_last)begin
                        load_active<=0;o_load_done<=1;
                        if(load_line)begin line_row[load_bank]<=load_row;line_valid[load_bank]<=1;end
                        else begin tag_ready[load_bank]<=1;tag_pending[load_bank]<=0;end
                    end else load_beat<=load_beat+1'b1;
                end else if(i_load_vld && !load_active)o_load_error<=1;
                case(qstate)
                    Q_IDLE:if(i_lookup_req && !i_line_mode)begin
                        qa<=i_lookup_a;qb<=i_lookup_b;qs0<=i_lookup_x[10:6];
                        qs1<=(i_lookup_x==1919)?5'd29:(i_lookup_x+11'd1)>>6;
                        qseq<=i_lookup_seq;qstate<=Q_MATCH;
                    end
                    Q_MATCH:begin
                        for(k=0;k<4;k=k+1)begin
                            cmp_row=k>=2?qb:qa;cmp_seg=(k%2)?qs1:qs0;
                            for(g=0;g<12;g=g+1)begin
                                found=0;sel=0;
                                for(j=0;j<8;j=j+1)begin
                                    idx=2*(g*8+j)+cmp_row[0];
                                    if(tag_valid[idx] && tag_row[idx]==cmp_row && tag_seg[idx]==cmp_seg)
                                        begin found=1;sel=idx;end
                                end
                                match_hit[k][g]<=found;match_id[k*12+g]<=sel;
                            end
                        end
                        qstate<=Q_SELECT;
                    end
                    Q_SELECT:begin
                        lookup_same_row<=qa==qb;lookup_same_seg<=qs0==qs1;
                        for(k=0;k<4;k=k+1)begin
                            found=0;sel=0;
                            for(g=0;g<12;g=g+1)if(match_hit[k][g])begin
                                found=1;sel=match_id[k*12+g];
                            end
                            qid[k]<=sel;qfound[k]<=found;
                        end
                        qwhich<=0;qstate<=Q_CHECK;
                    end
                    Q_CHECK:begin
                        // Reuse duplicate neighbours allocated earlier in this batch.
                        // Keep the original largest-earlier-k priority.
                        // The equality flags are stable throughout this lookup.
                        found=local_check_found;sel=local_check_id;
                        if(found)begin
                            qid[qwhich]<=sel;qfound[qwhich]<=1;
                            if(qwhich==3)qstate<=Q_DONE;else qwhich<=qwhich+1'b1;
                        end else qstate<=Q_ELIG;
                    end
                    // P6: the same two stages are owned by local groups.
                    Q_ELIG:qstate<=Q_GROUP;
                    Q_GROUP:qstate<=Q_VICTIM;
                    Q_VICTIM:begin
                        for(g=0;g<12;g=g+1)
                            tree[4+g]={victim_hit[g],victim_age[g],victim_id[g]};
                        // 12 leaves: reduce three groups of four, then final two.
                        tree[4]=older(older(tree[4],tree[5]),older(tree[6],tree[7]));
                        tree[5]=older(older(tree[8],tree[9]),older(tree[10],tree[11]));
                        tree[6]=older(older(tree[12],tree[13]),older(tree[14],tree[15]));
                        tree[1]=older(older(tree[4],tree[5]),tree[6]);
                        chosen<=tree[1][7:0];chosen_ok<=tree[1][30];qstate<=Q_ALLOC;
                    end
                    Q_ALLOC:begin
                        if(chosen_ok)begin
                            tag_valid[chosen]<=1;tag_ready[chosen]<=0;tag_pending[chosen]<=1;
                            tag_row[chosen]<=missing_row;tag_seg[chosen]<=missing_seg;
                            fetch_fifo[fetch_wr]<=chosen;fetch_wr<=fetch_wr+1'b1;
                            qid[qwhich]<=chosen;qfound[qwhich]<=1;
                            if(qwhich==3)qstate<=Q_DONE;
                            else begin qwhich<=qwhich+1'b1;qstate<=Q_CHECK;end
                        end else qstate<=Q_CHECK;
                    end
                    Q_DONE:begin
                        o_id_a0<=qid[0];o_id_a1<=qid[1];o_id_b0<=qid[2];o_id_b1<=qid[3];
                        o_lookup_done<=1;qstate<=Q_IDLE;
                    end
                    default:qstate<=Q_IDLE;
                endcase
            end
        end
    end
endmodule

