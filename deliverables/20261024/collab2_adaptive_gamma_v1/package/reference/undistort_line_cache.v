// 四行参数化缓存；每行 120 个 256bit 块，返回拍无回压。
module undistort_line_cache #(
    parameter LINES_PER_SET = 2
)(
    input  wire         clk,
    input  wire         rst_n,
    input  wire         i_frame_clear,
    input  wire         i_load_begin,
    input  wire [7:0]   i_load_bank,
    input  wire [10:0]  i_load_row,
    input  wire         i_load_vld,
    input  wire [255:0] i_load_data,
    input  wire         i_load_last,
    output reg          o_load_done,
    output reg          o_load_error,
    input  wire [10:0]  i_query_row_a,
    input  wire [10:0]  i_query_row_b,
    output reg          o_hit_a,
    output reg          o_hit_b,
    output reg  [7:0]   o_bank_a,
    output reg  [7:0]   o_bank_b,
    input  wire [10:0]  i_prefetch_row,
    output reg          o_prefetch_hit,
    input  wire         i_sample_req,
    input  wire [7:0]   i_sample_bank_a,
    input  wire [7:0]   i_sample_bank_b,
    input  wire [10:0]  i_sample_x,
    output reg          o_sample_valid,
    output reg [15:0]   o_p00,
    output reg [15:0]   o_p01,
    output reg [15:0]   o_p10,
    output reg [15:0]   o_p11
);
    localparam BANKS = 2 * LINES_PER_SET;
    reg [BANKS-1:0] tag_valid;
    reg [10:0] tag_row [0:BANKS-1];
    reg load_active;
    reg [7:0] load_bank;
    reg [10:0] load_row;
    reg [6:0] load_beat;
    wire load_write = load_active && i_load_vld && load_beat < 7'd120;

    reg sample_first_pending, sample_output_pending;
    reg [7:0] sample_a, sample_b;
    reg [10:0] sample_x;
    reg [10:0] next_x;
    wire [6:0] read_index = i_sample_req ? i_sample_x[10:4] : next_x[10:4];
    wire read_enable = i_sample_req || sample_first_pending;
    wire [255:0] read_words [0:BANKS-1];
    reg [255:0] first_a, first_b;
    wire [255:0] current_a = read_words[sample_a];
    wire [255:0] current_b = read_words[sample_b];
    integer q;

    genvar g;
    generate for (g=0; g<BANKS; g=g+1) begin: BANK
        reg [255:0] ram [0:119];
        reg [255:0] read_word;
        always @(posedge clk) begin
            if (load_write && load_bank == g)
                ram[load_beat] <= i_load_data;
            if (read_enable)
                read_word <= ram[read_index];
        end
        assign read_words[g] = read_word;
    end endgenerate

    always @* begin
        o_hit_a=0; o_hit_b=0; o_prefetch_hit=0;
        o_bank_a=0; o_bank_b=0;
        for (q=0;q<BANKS;q=q+1) begin
            if (tag_valid[q] && tag_row[q] == i_query_row_a) begin
                o_hit_a=1; o_bank_a=q;
            end
            if (tag_valid[q] && tag_row[q] == i_query_row_b) begin
                o_hit_b=1; o_bank_b=q;
            end
            if (tag_valid[q] && tag_row[q] == i_prefetch_row)
                o_prefetch_hit=1;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tag_valid <= 0;
            load_active <= 0;
            load_bank <= 0;
            load_row <= 0;
            load_beat <= 0;
            o_load_done <= 0;
            o_load_error <= 0;
            sample_first_pending <= 0; sample_output_pending <= 0;
            sample_a <= 0; sample_b <= 0;
            sample_x <= 0; next_x <= 0;
            first_a <= 0; first_b <= 0;
            o_sample_valid <= 0;
            o_p00 <= 0; o_p01 <= 0;
            o_p10 <= 0; o_p11 <= 0;
        end else begin
            o_load_done <= 0;
            o_load_error <= 0;
            o_sample_valid <= 0;
            if (i_frame_clear) tag_valid <= 0;
            if (i_load_begin) begin
                if (load_active || i_load_bank >= BANKS || i_load_row > 11'd1079) begin
                    o_load_error <= 1;
                end else begin
                    load_active <= 1;
                    load_bank <= i_load_bank;
                    load_row <= i_load_row;
                    load_beat <= 0;
                    tag_valid[i_load_bank] <= 0;
                end
            end
            if (load_active && i_load_vld) begin
                if (load_beat >= 7'd120 || i_load_last != (load_beat == 7'd119)) begin
                    o_load_error <= 1;
                    load_active <= 0;
                    tag_valid[load_bank] <= 0;
                end else if (i_load_last) begin
                    load_active <= 0;
                    tag_row[load_bank] <= load_row;
                    tag_valid[load_bank] <= 1;
                    o_load_done <= 1;
                end else load_beat <= load_beat + 1'b1;
            end
            // 同一 RAM 端口交替读取当前块和相邻块；每两拍接受一个新像素。
            sample_first_pending <= i_sample_req;
            sample_output_pending <= sample_first_pending;
            if (i_sample_req) begin
                sample_a <= i_sample_bank_a;
                sample_b <= i_sample_bank_b;
                sample_x <= i_sample_x;
                next_x <= (i_sample_x == 11'd1919) ? 11'd1919 : i_sample_x + 1'b1;
            end
            if (sample_first_pending) begin
                first_a <= current_a;
                first_b <= current_b;
            end
            if (sample_output_pending) begin
                o_p00 <= first_a[16*sample_x[3:0] +: 16];
                o_p10 <= first_b[16*sample_x[3:0] +: 16];
                o_p01 <= current_a[16*next_x[3:0] +: 16];
                o_p11 <= current_b[16*next_x[3:0] +: 16];
                o_sample_valid <= 1;
            end
        end
    end
endmodule
