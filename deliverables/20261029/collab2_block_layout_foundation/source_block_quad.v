// Four bilinear neighbours in the 16x8 block layout. The source storage row
// decreases for the lower image neighbour, matching C63's row inversion.
module source_block_quad (
    input  wire [10:0] x,
    input  wire [10:0] y_storage,
    output wire [14:0] block_00,block_01,block_10,block_11,
    output wire [2:0] beat_top,beat_bottom,
    output wire [3:0] lane_left,lane_right,
    output wire valid
);
    wire [6:0] bx = x[10:4];
    wire [7:0] by = y_storage[10:3];
    wire [14:0] origin = by * 8'd120 + bx;
    wire cross_x = x[3:0] == 4'd15 && x != 11'd1919;
    wire cross_y = y_storage[2:0] == 3'd0 && y_storage != 11'd0;
    wire [10:0] bottom_row = y_storage == 0 ? 11'd0 : y_storage - 11'd1;
    wire [10:0] right_x = x == 11'd1919 ? x : x + 11'd1;
    assign valid = x < 11'd1920 && y_storage < 11'd1080;
    assign block_00 = origin;
    assign block_01 = origin + {14'd0,cross_x};
    assign block_10 = origin - (cross_y ? 15'd120 : 15'd0);
    assign block_11 = block_10 + {14'd0,cross_x};
    assign beat_top = y_storage[2:0];
    assign beat_bottom = bottom_row[2:0];
    assign lane_left = x[3:0];
    assign lane_right = right_x[3:0];
endmodule
