`include "source/rtl/video_contract.vh"
`timescale 1ns / 1ps
// Streaming 2x2 Bayer interpolation, one pixel per PCLK. Two line memories are
// inferred as simple dual-port RAM. The first output row uses input rows 0/1.
// Right/bottom edges reuse the last valid 2x2 window, so every frame remains
// WIDTH x HEIGHT. No Bayer samples are discarded and no spatial scaling occurs.
module raw8_to_rgb565 #(
    parameter WIDTH = `VC_WIDTH,
    parameter HEIGHT = `VC_HEIGHT,
    // Leave time for the example's DDR line writer after the final RGB pixel.
    parameter FRAME_GUARD = 512,
    // 0: BGGR, 1: GBRG, 2: GRBG, 3: RGGB (top-left Bayer sample).
    parameter [1:0] BAYER_PHASE = 2'd0
) (
    input wire pclk,
    input wire rst_n,
    input wire vs_in,
    input wire de_in,
    input wire [7:0] raw_in,
    output reg vs_out,
    output reg de_out,
    output reg [15:0] rgb_out
);
    reg [7:0] even_line [0:WIDTH-1];
    reg [7:0] odd_line [0:WIDTH-1];
    reg [11:0] x;
    reg [11:0] y;
    reg vs_d;
    reg de_d;
    reg armed;
    reg flushing;
    reg [11:0] flush_x;
    reg [2:0] flush_wait;
    reg [7:0] top;
    reg [7:0] bottom;
    reg sample_valid;
    reg [11:0] sample_x;
    reg [11:0] sample_y;
    reg [7:0] top_left;
    reg [7:0] bottom_left;
    reg sample_valid_d;
    reg [15:0] last_rgb;
    reg [7:0] r;
    reg [7:0] b;
    reg [8:0] g_sum;
    reg sync_pending;
    reg [11:0] sync_guard;
    reg [4:0] sync_width;
    wire frame_edge = vs_in && !vs_d;
    wire [11:0] top_y = sample_y - 12'd1;
    wire [11:0] left_x = sample_x - 12'd1;
    wire [1:0] phase = {top_y[0], left_x[0]} ^ BAYER_PHASE;

    // Memory reads have one clock latency. Keep their enables identical to
    // sample_valid, and never reset the memories (which would prevent BRAM use).
    always @(posedge pclk) begin
        if (de_in && armed && !flushing && y < HEIGHT && x < WIDTH) begin
            if (y[0]) begin
                top <= even_line[x];
                odd_line[x] <= raw_in;
            end else begin
                top <= odd_line[x];
                even_line[x] <= raw_in;
            end
            bottom <= raw_in;
        end else if (flushing && flush_x < WIDTH) begin
            if ((HEIGHT % 2) == 0) begin
                top <= even_line[flush_x];
                bottom <= odd_line[flush_x];
            end else begin
                top <= odd_line[flush_x];
                bottom <= even_line[flush_x];
            end
        end
    end

    always @(posedge pclk) begin
        if (!rst_n) begin
            x <= 12'd0;
            y <= 12'd0;
            vs_d <= 1'b0;
            de_d <= 1'b0;
            armed <= 1'b0;
            flushing <= 1'b0;
            flush_x <= 12'd0;
            flush_wait <= 3'd0;
            sample_valid <= 1'b0;
            sample_x <= 12'd0;
            sample_y <= 12'd0;
        end else begin
            vs_d <= vs_in;
            de_d <= de_in;
            sample_valid <= 1'b0;
            // VSYNC may occur immediately after the last HREF. Reset the
            // input coordinates on its edge, but do not abort the bottom row.
            // Do not gate capture by VSYNC level: it is a boundary signal.
            if (frame_edge) begin
                x <= 12'd0;
                y <= 12'd0;
                armed <= 1'b1;
            end else if (armed && !flushing && flush_wait == 0) begin
                if (de_in && y < HEIGHT && x < WIDTH)
                    x <= x + 12'd1;
                else if (!de_in && de_d) begin
                    x <= 12'd0;
                    y <= y + 12'd1;
                end
            end

            if (flushing) begin
                if (flush_x < WIDTH) begin
                    sample_valid <= 1'b1;
                    sample_x <= flush_x;
                    sample_y <= HEIGHT - 1;
                    flush_x <= flush_x + 12'd1;
                end else begin
                    flushing <= 1'b0;
                end
            end else if (flush_wait != 0) begin
                flush_wait <= flush_wait - 3'd1;
                if (flush_wait == 1) begin
                    flushing <= 1'b1;
                    flush_x <= 12'd0;
                end
            end else if (armed) begin
                if (de_in && y < HEIGHT && x < WIDTH) begin
                    sample_valid <= (y != 0);
                    sample_x <= x;
                    sample_y <= y;
                end else if (!de_in && de_d) begin
                    if (y == HEIGHT - 1)
                        flush_wait <= 3'd4;
                end
            end
        end
    end

    // Retiming the frame marker is as important as completing the last row:
    // passing sensor VSYNC straight through resets DDR addresses too early.
    // Assert one output marker after interpolation drains plus a DDR service
    // guard (512 / 84 MHz = 6.10 us). Vertical blanking is 40 sensor lines.
    always @(posedge pclk) begin
        if (!rst_n) begin
            vs_out <= 1'b0;
            sync_pending <= 1'b0;
            sync_guard <= 12'd0;
            sync_width <= 5'd0;
        end else begin
            if (sync_width != 0) begin
                sync_width <= sync_width - 5'd1;
                vs_out <= 1'b1;
            end else
                vs_out <= 1'b0;
            if (sync_pending) begin
                if (flushing || flush_wait != 0 || sample_valid || sample_valid_d || de_out)
                    sync_guard <= FRAME_GUARD;
                else if (sync_guard != 0)
                    sync_guard <= sync_guard - 12'd1;
                else begin
                    vs_out <= 1'b1;
                    sync_width <= 5'd15;
                    sync_pending <= 1'b0;
                end
            end
            if (frame_edge) begin
                sync_pending <= 1'b1;
                sync_guard <= FRAME_GUARD;
            end
        end
    end

    always @* begin
        r = bottom;
        b = top_left;
        g_sum = {1'b0, top} + {1'b0, bottom_left};
        case (phase)
            2'd0: begin
                r = bottom; b = top_left;
                g_sum = {1'b0, top} + {1'b0, bottom_left};
            end
            2'd1: begin
                r = bottom_left; b = top;
                g_sum = {1'b0, top_left} + {1'b0, bottom};
            end
            2'd2: begin
                r = top; b = bottom_left;
                g_sum = {1'b0, top_left} + {1'b0, bottom};
            end
            2'd3: begin
                r = top_left; b = bottom;
                g_sum = {1'b0, top} + {1'b0, bottom_left};
            end
        endcase
    end

    always @(posedge pclk) begin
        if (!rst_n) begin
            de_out <= 1'b0;
            rgb_out <= 16'd0;
            last_rgb <= 16'd0;
            sample_valid_d <= 1'b0;
            top_left <= 8'd0;
            bottom_left <= 8'd0;
        end else begin
            de_out <= 1'b0;
            sample_valid_d <= sample_valid;
            if (sample_valid) begin
                top_left <= top;
                bottom_left <= bottom;
                if (sample_x != 0) begin
                    rgb_out <= {r[7:3], g_sum[8:3], b[7:3]};
                    last_rgb <= {r[7:3], g_sum[8:3], b[7:3]};
                    de_out <= 1'b1;
                end
            end else if (sample_valid_d) begin
                rgb_out <= last_rgb;
                de_out <= 1'b1;
            end
        end
    end
endmodule
