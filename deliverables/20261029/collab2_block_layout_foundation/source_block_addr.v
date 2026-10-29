// RGB565 source storage: 120 blocks per band, each 16x8 pixels / 8 DDR beats.
// y_storage follows the existing C63 bottom-up row numbering.
module source_block_addr (
    input  wire [10:0] x,
    input  wire [10:0] y_storage,
    output wire [19:0] block_word_addr,
    output wire [19:0] pixel_word_addr,
    output wire [2:0] beat_in_block,
    output wire [3:0] pixel_in_beat,
    output wire valid
);
    wire [6:0] block_x = x[10:4];
    wire [7:0] block_y = y_storage[10:3];
    wire [14:0] block_index = block_y * 8'd120 + block_x;
    assign valid = x < 11'd1920 && y_storage < 11'd1080;
    assign block_word_addr = {block_index, 6'b0};
    assign pixel_word_addr = block_word_addr + {14'd0, y_storage[2:0], 3'b0}
                           + {17'd0, x[3:1]};
    assign beat_in_block = y_storage[2:0];
    assign pixel_in_beat = x[3:0];
endmodule
