// Shared compile-time contract for the 1920x1080 RGB565 capture/display path.
// Frame counts assume two 16-bit pixels per 32-bit DDR word. Slot/base values
// must match frame_bank_ctrl and correction brokerage. HDMI timing is 1080p30;
// camera mode and PLL/IP settings remain fixed outside run-time quality control.
`ifndef VIDEO_CONTRACT_VH
`define VIDEO_CONTRACT_VH
`define VC_WIDTH 1920
`define VC_HEIGHT 1080
`define VC_PIXEL_BITS 16
`define VC_SLOT_WORD_BITS 20
`define VC_ROW_WORDS (`VC_WIDTH/2)
`define VC_FRAME_WORDS (`VC_ROW_WORDS*`VC_HEIGHT)
`define VC_CORR_BASE 3'd4
`define VC_RD_SLOT_BASE 3'd4
`define VC_NATIVE_BURST_BEATS 16
`define VC_WRITE_BURST_BEATS 8
`define VC_H_TOTAL 2200
`define VC_H_FP 88
`define VC_H_BP 148
`define VC_H_SYNC 44
`define VC_V_TOTAL 1125
`define VC_V_FP 4
`define VC_V_BP 36
`define VC_V_SYNC 5
`endif
