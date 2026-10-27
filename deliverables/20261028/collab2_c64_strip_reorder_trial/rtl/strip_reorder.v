module strip_reorder #(
    parameter WIDTH = 1920,
    parameter HEIGHT = 1080,
    parameter STRIP_H = 16,
    parameter AW = $clog2(WIDTH * STRIP_H),
    parameter XW = $clog2(WIDTH),
    parameter YW = $clog2(HEIGHT + 1),
    parameter HW = $clog2(STRIP_H + 1)
) (
    input wire clk,
    input wire rst_n,
    input wire i_frame_start,
    input wire i_valid,
    output wire o_ready,
    input wire [15:0] i_pixel,
    output reg o_valid,
    input wire i_ready,
    output reg [15:0] o_pixel,
    output reg [XW-1:0] o_x,
    output reg [YW-1:0] o_y,
    output reg o_sof,
    output reg o_eof,
    output reg o_input_done,
    output reg o_output_done
);
    localparam [1:0] FREE=0, FILL=1, READY=2, DRAIN=3;
    reg [1:0] state0, state1;
    reg [YW-1:0] base0, base1;
    reg [HW-1:0] height0, height1;
    reg [15:0] bank0 [0:WIDTH*STRIP_H-1];
    reg [15:0] bank1 [0:WIDTH*STRIP_H-1];

    reg wr_bank;
    reg [AW-1:0] wr_addr;
    reg [XW-1:0] wr_col;
    reg [HW-1:0] wr_row;
    reg [YW-1:0] wr_base;
    wire [HW-1:0] wr_height =
        HEIGHT - wr_base < STRIP_H ? HEIGHT - wr_base : STRIP_H;
    wire write_fire = i_valid && o_ready;
    wire last_column = wr_col == WIDTH-1;
    wire last_row = wr_row == wr_height-1'b1;
    assign o_ready = !i_frame_start && !o_input_done &&
        (wr_bank ? state1==FREE || state1==FILL :
                   state0==FREE || state0==FILL);

    reg rd_next_bank, rd_active, rd_bank;
    reg [AW-1:0] rd_addr;
    reg [XW-1:0] rd_x;
    reg [HW-1:0] rd_row;
    reg [YW-1:0] rd_base;
    reg [HW-1:0] rd_height;
    reg out_bank;
    reg out_last;
    wire output_slot = !o_valid || i_ready;
    wire start_read = !rd_active && !o_output_done && output_slot &&
        (rd_next_bank ? state1==READY : state0==READY);
    wire read_fire = !i_frame_start && output_slot && (rd_active || start_read);
    wire read_bank = rd_active ? rd_bank : rd_next_bank;
    wire [AW-1:0] read_addr = rd_active ? rd_addr : {AW{1'b0}};
    wire [XW-1:0] read_x = rd_active ? rd_x : {XW{1'b0}};
    wire [YW-1:0] read_y = rd_active ? rd_base + rd_row :
        (rd_next_bank ? base1 : base0);
    wire [HW-1:0] read_height = rd_active ? rd_height :
        (rd_next_bank ? height1 : height0);
    wire read_last = rd_active ?
        (rd_addr == WIDTH * rd_height - 1) :
        (WIDTH * read_height == 1);

    always @(posedge clk) begin
        if (write_fire && !wr_bank) bank0[wr_addr] <= i_pixel;
        if (write_fire && wr_bank) bank1[wr_addr] <= i_pixel;
        if (read_fire && !read_bank) o_pixel <= bank0[read_addr];
        if (read_fire && read_bank) o_pixel <= bank1[read_addr];
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state0<=FREE; state1<=FREE;
            base0<=0; base1<=0; height0<=0; height1<=0;
            wr_bank<=0; wr_addr<=0; wr_col<=0; wr_row<=0; wr_base<=0;
            rd_next_bank<=0; rd_active<=0; rd_bank<=0;
            rd_addr<=0; rd_x<=0; rd_row<=0; rd_base<=0; rd_height<=0;
            out_bank<=0; out_last<=0;
            o_valid<=0; o_x<=0; o_y<=0; o_sof<=0; o_eof<=0;
            o_input_done<=0; o_output_done<=0;
        end else if (i_frame_start) begin
            state0<=FREE; state1<=FREE;
            wr_bank<=0; wr_addr<=0; wr_col<=0; wr_row<=0; wr_base<=0;
            rd_next_bank<=0; rd_active<=0;
            o_valid<=0; o_input_done<=0; o_output_done<=0;
        end else begin
            if (write_fire) begin
                if (wr_bank) begin
                    if (state1==FREE) begin
                        base1<=wr_base; height1<=wr_height;
                    end
                    state1<=last_column && last_row ? READY : FILL;
                end else begin
                    if (state0==FREE) begin
                        base0<=wr_base; height0<=wr_height;
                    end
                    state0<=last_column && last_row ? READY : FILL;
                end
                if (last_row) begin
                    wr_row<=0;
                    if (last_column) begin
                        wr_addr<=0; wr_col<=0;
                        wr_base<=wr_base+wr_height;
                        wr_bank<=!wr_bank;
                        if (wr_base+wr_height==HEIGHT) o_input_done<=1;
                    end else begin
                        wr_col<=wr_col+1'b1;
                        wr_addr<=wr_col+1'b1;
                    end
                end else begin
                    wr_row<=wr_row+1'b1;
                    wr_addr<=wr_addr+WIDTH;
                end
            end

            if (o_valid && i_ready && out_last) begin
                if (out_bank) state1<=FREE;
                else state0<=FREE;
                rd_next_bank<=!rd_next_bank;
                if (o_eof) o_output_done<=1;
            end
            if (read_fire) begin
                o_valid<=1;
                o_x<=read_x; o_y<=read_y;
                o_sof<=read_x==0 && read_y==0;
                o_eof<=read_x==WIDTH-1 && read_y==HEIGHT-1;
                out_bank<=read_bank;
                out_last<=read_last;
                rd_bank<=read_bank;
                rd_base<=rd_active ? rd_base : read_y;
                rd_height<=read_height;
                rd_active<=!read_last;
                rd_addr<=read_addr+1'b1;
                if (read_x==WIDTH-1) begin
                    rd_x<=0;
                    rd_row<=rd_active ? rd_row+1'b1 : 1;
                end else begin
                    rd_x<=read_x+1'b1;
                    if (!rd_active) rd_row<=0;
                end
                if (start_read) begin
                    if (read_bank) state1<=DRAIN;
                    else state0<=DRAIN;
                end
            end else if (output_slot) begin
                o_valid<=0;
            end
        end
    end
endmodule
