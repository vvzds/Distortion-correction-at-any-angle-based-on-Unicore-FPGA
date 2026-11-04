`timescale 1ns/1ps
// Five active-low board keys share one control-clock synchronizer/debouncer.
// KEY1 toggles the live BNO085 pose map. The pose map always composes against
// the last accepted host matrix, so the key cannot discard host crop/zoom data.
module feature_key_control #(
    parameter DEBOUNCE_CYCLES = 2500000
)(
    input wire clk,
    input wire rst_n,
    input wire [4:0] key_n,
    input wire affine_pc_update,
    input wire affine_pc_enable,
    input wire quality_pc_update,
    input wire osd_pc_update,
    input wire osd_pc_visible,
    output reg brown_enable,
    output reg affine_enable,
    output reg affine_capture_toggle,
    output reg stabilization_lock_request,
    output reg gamma_enable,
    output reg [1:0] quality_profile,
    output reg osd_visible
);
    reg [4:0] key_meta, key_sync, key_stable, key_stable_d;
    reg [21:0] debounce_count [0:4];
    wire [4:0] key_press = key_stable_d & ~key_stable;
    integer i;

    // Synchronize the physical pins, then accept a state only after it remains
    // unchanged for the configured debounce interval.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            key_meta <= 5'b11111;
            key_sync <= 5'b11111;
            key_stable <= 5'b11111;
            key_stable_d <= 5'b11111;
            for (i=0; i<5; i=i+1) debounce_count[i] <= 0;
        end else begin
            key_meta <= key_n;
            key_sync <= key_meta;
            key_stable_d <= key_stable;
            for (i=0; i<5; i=i+1) begin
                if (key_sync[i] == key_stable[i]) begin
                    debounce_count[i] <= 0;
                end else if (debounce_count[i] >= DEBOUNCE_CYCLES-1) begin
                    key_stable[i] <= key_sync[i];
                    debounce_count[i] <= 0;
                end else begin
                    debounce_count[i] <= debounce_count[i] + 1'b1;
                end
            end
        end
    end

    // Function state changes only once per debounced press. The key and host
    // command update the same affine-enable state and capture handshake.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            brown_enable <= 1'b1;
            affine_enable <= 1'b0;
            affine_capture_toggle <= 1'b0;
            stabilization_lock_request <= 1'b0;
            gamma_enable <= 1'b1;
            quality_profile <= 2'd0;
            osd_visible <= 1'b0;
        end else begin
            if (key_press[0]) brown_enable <= ~brown_enable;
            if (affine_pc_update) begin
                affine_enable <= affine_pc_enable;
                stabilization_lock_request <= affine_pc_enable;
            end
            if (key_press[1]) begin
                affine_enable <= ~affine_enable;
                stabilization_lock_request <= ~affine_enable;
                affine_capture_toggle <= ~affine_capture_toggle;
            end
            if (key_press[2]) gamma_enable <= ~gamma_enable;

            if (key_press[3]) begin
                if (quality_profile == 2'd3) quality_profile <= 2'd0;
                else quality_profile <= quality_profile + 1'b1;
            end
            if (quality_pc_update) quality_profile <= 2'd0;

            if (osd_pc_update) osd_visible <= osd_pc_visible;
            else if (key_press[4]) osd_visible <= ~osd_visible;
        end
    end
endmodule

// Apply only the feature switches that are independent of host geometry.
// The host/IMU affine matrix is always preserved: KEY1 selects live IMU
// mapping, while host 0x10 packets remain effective in either KEY1 state.
module feature_config_gate(
    input  wire [511:0] correction_config,
    input  wire brown_enable,
    input  wire gamma_enable,
    output reg  [511:0] feature_config
);
    always @* begin
        feature_config = correction_config;
        if (!brown_enable) begin
            feature_config[10*32+:32] = 32'd0;
            feature_config[11*32+:32] = 32'd0;
            feature_config[12*32+:32] = 32'd0;
            feature_config[13*32+:32] = 32'd0;
        end
        if (!gamma_enable)
            feature_config[14*32] = 1'b0;
    end
endmodule
