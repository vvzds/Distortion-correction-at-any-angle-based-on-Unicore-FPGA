`timescale 1ns/1ps
// rect_wr_if：RGB565像素对打包、D3目标槽申请、C3整帧顺序写。
// 单一125MHz时钟域；输入标志应已在顶层与Gamma输出对齐。
// RAM与预读头寄存器合计最多2048个完整字，半像素单独暂存。
// 无输入回压：容量保证依赖外部服务条件，不声称任意等待下零丢失。
module rect_wr_if (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        i_pix_vld,
    input  wire [15:0] i_pix,
    input  wire        i_sop,
    input  wire        i_eop,
    input  wire        i_sof,
    input  wire        i_eof,
    output reg         o_corr_wr_slot_req,
    input  wire        i_corr_wr_slot_gnt,
    input  wire [2:0]  i_corr_wr_slot,
    output reg         o_corr_wr_commit,
    output reg         o_corr_wr_req,
    output reg  [23:0] o_corr_wr_addr,
    output reg  [31:0] o_corr_wr_data,
    input  wire        i_corr_wr_gnt
);
    localparam [20:0] LAST_PIXEL = 21'd2073599;
    localparam [19:0] LAST_WORD  = 20'd1036799;
    localparam [1:0] IDLE=2'd0, WAIT_SLOT=2'd1,
                     WRITE_FRAME=2'd2, COMMIT_FRAME=2'd3;

    reg [1:0] state;
    reg [1:0] queued_frames;
    reg [2:0] target_slot;
    reg [23:0] write_addr;
    reg [19:0] write_index;

    // 输入计数指向下一个有效像素；1920为偶数，最低位即列奇偶。
    // sop/eop不参与控制；其正确性由上游契约与TB检查。
    reg input_open;
    reg [20:0] pixel_index;
    reg [15:0] low_pixel;

    // 同步读RAM，不复位存储内容；head_valid屏蔽未初始化的头数据。
    reg [31:0] fifo_mem [0:2047];
    reg [10:0] fifo_wr_ptr, fifo_rd_ptr;
    reg [11:0] fifo_count;
    reg [31:0] head_data;
    reg head_valid;

    // 异常后停止本客户端，只有系统整体复位才恢复；绝不提交残帧。
    // 这是内部诊断状态，未新增或更改任何冻结接口。
    reg fault;
    wire frame_start = i_pix_vld && i_sof && !input_open;
    wire input_error = i_pix_vld &&
                       ((!input_open && !i_sof) ||
                        (input_open && i_sof) ||
                        (i_eof != (input_open && pixel_index == LAST_PIXEL)));
    wire slot_accept = o_corr_wr_slot_req && i_corr_wr_slot_gnt;
    wire write_accept = o_corr_wr_req && i_corr_wr_gnt;
    wire fifo_full = (fifo_count + {11'd0,head_valid}) == 12'd2048;
    wire push_candidate = i_pix_vld && input_open && pixel_index[0] &&
                          !input_error && !fault;
    wire overflow = push_candidate && fifo_full && !write_accept;
    wire push = push_candidate && (!fifo_full || write_accept);
    wire prefetch = !fault && (!head_valid || write_accept) && fifo_count != 0;
    wire queue_error = frame_start && queued_frames == 2'd3 && !slot_accept;
    wire slot_error = slot_accept && !i_corr_wr_slot[2];

    always @* begin
        o_corr_wr_slot_req = rst_n && !fault && state == WAIT_SLOT;
        o_corr_wr_req = rst_n && !fault && state == WRITE_FRAME && head_valid;
        o_corr_wr_commit = rst_n && !fault && state == COMMIT_FRAME;
        o_corr_wr_addr = write_addr;
        o_corr_wr_data = head_valid ? head_data : 32'd0;
    end

    // 一写一同步读，预读端可在有积压时每拍替换一个已受理字。
    // head与RAM的总占用限制为2048；满且同拍出队时允许继续入队。
    always @(posedge clk) begin
        if (rst_n && push)
            fifo_mem[fifo_wr_ptr] <= {i_pix,low_pixel};
        if (rst_n && prefetch)
            head_data <= fifo_mem[fifo_rd_ptr];
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            fifo_wr_ptr <= 11'd0;
            fifo_rd_ptr <= 11'd0;
            fifo_count <= 12'd0;
            head_valid <= 1'b0;
        end else begin
            if (push) fifo_wr_ptr <= fifo_wr_ptr + 1'b1;
            if (prefetch) fifo_rd_ptr <= fifo_rd_ptr + 1'b1;
            case ({push,prefetch})
                2'b10: fifo_count <= fifo_count + 1'b1;
                2'b01: fifo_count <= fifo_count - 1'b1;
                default: ;
            endcase
            if (prefetch) head_valid <= 1'b1;
            else if (write_accept) head_valid <= 1'b0;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            input_open <= 1'b0;
            pixel_index <= 21'd0;
            low_pixel <= 16'd0;
        end else if (i_pix_vld && !fault && !input_error) begin
            if (!input_open) begin
                input_open <= 1'b1;
                pixel_index <= 21'd1;
                low_pixel <= i_pix;
            end else begin
                if (!pixel_index[0]) low_pixel <= i_pix;
                if (pixel_index == LAST_PIXEL) begin
                    input_open <= 1'b0;
                    pixel_index <= 21'd0;
                end else pixel_index <= pixel_index + 1'b1;
            end
        end
    end

    // 只记录已出现但尚未分配目标槽的SOF，不把下一帧写到当前槽。
    // 完整帧长远大于FIFO，合法服务情况下此队列最多积压一帧。
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) queued_frames <= 2'd0;
        else if (!fault && !input_error) begin
            case ({frame_start,slot_accept})
                2'b10: queued_frames <= queued_frames + 1'b1;
                2'b01: queued_frames <= queued_frames - 1'b1;
                default: ;
            endcase
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            target_slot <= 3'd0;
            write_addr <= 24'd0;
            write_index <= 20'd0;
        end else if (!fault) begin
            case (state)
                IDLE: begin
                    if (queued_frames != 0 || frame_start) state <= WAIT_SLOT;
                end
                WAIT_SLOT: begin
                    if (slot_accept && !slot_error) begin
                        target_slot <= i_corr_wr_slot;
                        write_addr <= {1'b0,i_corr_wr_slot,20'd0};
                        write_index <= 20'd0;
                        state <= WRITE_FRAME;
                    end
                end
                WRITE_FRAME: begin
                    if (write_accept) begin
                        if (write_index == LAST_WORD) state <= COMMIT_FRAME;
                        else begin
                            write_index <= write_index + 1'b1;
                            write_addr <= write_addr + 1'b1;
                        end
                    end
                end
                // 末字受理后的周期输出commit；下一申请经过IDLE隔开。
                // 不检查共享FIFO为空，已预读的下一帧数据继续保留。
                COMMIT_FRAME: state <= IDLE;
                default: state <= IDLE;
            endcase
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) fault <= 1'b0;
        else if (input_error || overflow || queue_error || slot_error) fault <= 1'b1;
    end

`ifdef SIMULATION
    // 仅仿真计错，不引入综合用调试端口，不假装硬件具有输入回压。
    integer sim_error_count;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) sim_error_count <= 0;
        else if (!fault && (input_error || overflow || queue_error || slot_error)) begin
            sim_error_count <= sim_error_count + 1;
            $display("RECT_WR_IF ERROR input=%b overflow=%b queue=%b slot=%b",
                     input_error,overflow,queue_error,slot_error);
        end
    end
`endif
endmodule
