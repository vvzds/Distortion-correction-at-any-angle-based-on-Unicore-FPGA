`timescale 1ns/1ps
// Five active-low board keys share one control-clock synchronizer/debouncer.
// KEY0 toggles Brown distortion, KEY1 toggles live affine/IMU stabilization,
// KEY2 toggles adaptive Gamma, KEY3 cycles quality presets, and KEY4 toggles
// OSD visibility. Host quality/OSD commands resynchronize their key controls.
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

    // Function state changes only once per debounced press. The affine key
    // captures a fresh IMU reference pose when enabling stabilization.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            brown_enable <= 1'b1;
            affine_enable <= 1'b0;
            affine_capture_toggle <= 1'b0;
            gamma_enable <= 1'b1;
            quality_profile <= 2'd0;
            osd_visible <= 1'b0;
        end else begin
            if (key_press[0]) brown_enable <= ~brown_enable;
            if (affine_pc_update) begin
                affine_enable <= affine_pc_enable;
            end else if (key_press[1]) begin
                affine_enable <= ~affine_enable;
                if (!affine_enable)
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
