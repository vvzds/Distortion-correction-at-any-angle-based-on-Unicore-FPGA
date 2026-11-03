// Production correction-path declarations and instances textually included by
// hdmi_ddr_ov5640_top. Host configuration, frame ownership, tile scheduling,
// DDR brokerage, counters and optional IMU mapping use the 125 MHz control/DDR
// domain. Display filters/OSD use the pixel domain in the top-level video path;
// preserve the explicit CDC handshakes where signals cross those boundaries.
`include "source/rtl/default_config.vh"
wire [511:0] host_config,correction_config;
reg [511:0] correction_config_pipe;
wire imu_map_config_update;
wire [511:0] published_config;
wire correction_busy,config_pending,core_fault;
wire [31:0] corrected_frames,frame_cycles,read_wait_cycles,write_wait_cycles;
wire [31:0] source_read_beats,invalid_pixel_count,patch_overflows;
wire [31:0] host_rx_errors,host_packet_count;
wire [15:0] active_config_sequence;
wire [1:0] adaptive_mode;
wire host_imu_map_enable,host_imu_map_update,host_imu_capture_toggle;
wire key_affine_enable,key_affine_capture_toggle;
wire imu_map_enable=key_affine_enable;
wire imu_capture_toggle=host_imu_capture_toggle^key_affine_capture_toggle;
wire imu_reference_valid,imu_map_valid,imu_map_busy;
wire [7:0] imu_capture_generation;
wire [31:0] correction_flags={14'd0,imu_map_valid,imu_capture_generation,imu_map_busy,imu_reference_valid,imu_map_enable,
    adaptive_mode,corr_protocol_error,core_fault,config_pending,correction_busy};
wire [383:0] imu_snapshot,imu_diagnostics;
wire [2:0] imu_baud_code; // protocol 0x23 selects BNO report mode on BNO firmware
wire imu_restart;
wire [1:0] host_denoise_level,host_sharpen_level;
wire [1:0] key_quality_profile;
wire [1:0] denoise_level=(key_quality_profile==0)?host_denoise_level:
                         (key_quality_profile==3)?2'd2:2'd1;
wire [1:0] sharpen_level=(key_quality_profile==0)?host_sharpen_level:
                          (key_quality_profile==1)?2'd0:2'd1;
wire osd_row_valid,host_osd_visible,key_osd_visible;
wire [4:0] board_key_n;
wire key_brown_enable,key_gamma_enable;
wire quality_update,osd_update;
wire [2:0] osd_row_index;
wire [383:0] osd_row_data;
reg feature_frame_brown_enable,feature_frame_gamma_enable;
wire [511:0] feature_config;
feature_config_gate u_feature_config_gate(
    .correction_config(correction_config),
    .brown_enable(feature_frame_brown_enable),
    .gamma_enable(feature_frame_gamma_enable),
    .feature_config(feature_config));
feature_key_control u_feature_key_control(
    .clk(corr_clk),.rst_n(corr_rst_n),.key_n(board_key_n),
    .affine_pc_update(host_imu_map_update),.affine_pc_enable(host_imu_map_enable),
    .quality_pc_update(quality_update),.osd_pc_update(osd_update),
    .osd_pc_visible(host_osd_visible),.brown_enable(key_brown_enable),
    .affine_enable(key_affine_enable),.affine_capture_toggle(key_affine_capture_toggle),
    .gamma_enable(key_gamma_enable),.quality_profile(key_quality_profile),
    .osd_visible(key_osd_visible));
always @(posedge corr_clk or negedge corr_rst_n) begin
    if (!corr_rst_n) begin
        feature_frame_brown_enable<=1'b1;
        feature_frame_gamma_enable<=1'b1;
        correction_config_pipe<=0;
    end else begin
        if (o_frame_update) begin
            feature_frame_brown_enable<=key_brown_enable;
            feature_frame_gamma_enable<=key_gamma_enable;
        end
        correction_config_pipe<=feature_config;
    end
end
bno085_bridge u_bno085(.clk(corr_clk),.rst_n(corr_rst_n),
    .miso(bno_miso),.int_n(bno_int_n),.sck(bno_sck),.mosi(bno_mosi),
    .cs_n(bno_cs_n),.sensor_rst_n(bno_rst_n),.wake_n(bno_wake_n),
    .mode(imu_baud_code),.restart(imu_restart),.frame_update(o_frame_update),
    .snapshot(imu_snapshot),.diagnostics(imu_diagnostics));
host_control u_host_control(
    .clk(corr_clk),.rst_n(corr_rst_n),.uart_rx(uart_rx),.uart_tx(uart_tx),
    .busy(correction_busy),.imu_snapshot(imu_snapshot),.imu_diagnostics(imu_diagnostics),
    .imu_baud_code(imu_baud_code),.imu_restart(imu_restart),
    .imu_map_enable(host_imu_map_enable),.imu_map_update(host_imu_map_update),
    .imu_capture_toggle(host_imu_capture_toggle),
    .denoise_level(host_denoise_level),.sharpen_level(host_sharpen_level),
    .quality_update(quality_update),.osd_update(osd_update),
    .osd_row_valid(osd_row_valid),.osd_visible(host_osd_visible),
    .osd_row_index(osd_row_index),.osd_row_data(osd_row_data),
    .published_cfg(published_config),
    .telemetry({correction_flags,patch_overflows,invalid_pixel_count,source_read_beats,
                write_wait_cycles,read_wait_cycles,frame_cycles,corrected_frames}),
    .cfg(host_config),.pending(config_pending),.active_sequence(active_config_sequence),
    .rx_errors(host_rx_errors),.valid_packets(host_packet_count)
);
imu_projective_map u_imu_projective_map(
    .clk(corr_clk),.rst_n(corr_rst_n),.enable(imu_map_enable),
    .capture_toggle(imu_capture_toggle),.imu_snapshot(imu_snapshot),
    .base_cfg(host_config),.base_sequence(active_config_sequence),.map_cfg(correction_config),
    .busy(imu_map_busy),.reference_valid(imu_reference_valid),.map_valid(imu_map_valid),
    .capture_generation(imu_capture_generation),.config_update(imu_map_config_update));
tile_engine u_tile_engine(
    .clk(corr_clk),.rst_n(corr_rst_n),.frame_update(o_frame_update),
    .cfg(correction_config_pipe),
    .config_pending(config_pending|imu_map_busy|imu_map_config_update),.busy(correction_busy),
    .src_req(corr_src_hold_req),.src_gnt(corr_src_hold_gnt),.src_slot(corr_src_slot),.src_rel(corr_src_rel),
    .rd_req(corr_rd_req),.rd_addr(corr_rd_addr),.rd_len(corr_rd_len),
    .rd_gnt(corr_rd_gnt),.rd_valid(corr_rd_vld),.rd_last(corr_rd_last),.rd_data(corr_rd_data),
    .slot_req(corr_wr_slot_req),.slot_gnt(corr_wr_slot_gnt),.slot(corr_wr_slot),
    .wr_req(corr_wr_req),.wr_addr(corr_wr_addr),.wr_data(corr_wr_data),.wr_gnt(corr_wr_gnt),
    .commit(corr_wr_commit),.published(corr_pub_pulse),
    .frame_count(corrected_frames),.last_cycles(frame_cycles),
    .last_rd_wait(read_wait_cycles),.last_wr_wait(write_wait_cycles),
    .last_read_beats(source_read_beats),.last_invalid(invalid_pixel_count),
    .overflow_tiles(patch_overflows),.protocol_fault(core_fault),.gamma_mode(adaptive_mode),
    .published_cfg(published_config)
);
