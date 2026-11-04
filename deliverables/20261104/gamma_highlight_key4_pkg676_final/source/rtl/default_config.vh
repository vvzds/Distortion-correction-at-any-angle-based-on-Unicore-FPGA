// Power-up camera/calibration configuration loaded by host_control after reset.
// DEFAULT_0..DEFAULT_15 are signed Q-format words in host protocol register
// order. They seed the same shadow/active path as a UART SET packet; keep the
// values synchronized with the calibration/default JSON supplied to the host.
localparam signed [31:0] DEFAULT_0 = 32'sd178042;
localparam signed [31:0] DEFAULT_1 = 32'sd0;
localparam signed [31:0] DEFAULT_2 = -32'sd614476;
localparam signed [31:0] DEFAULT_3 = 32'sd0;
localparam signed [31:0] DEFAULT_4 = 32'sd178078;
localparam signed [31:0] DEFAULT_5 = -32'sd395589;
localparam signed [31:0] DEFAULT_6 = 32'sd98809312;
localparam signed [31:0] DEFAULT_7 = 32'sd98789197;
localparam signed [31:0] DEFAULT_8 = 32'sd57903224;
localparam signed [31:0] DEFAULT_9 = 32'sd37269520;
localparam signed [31:0] DEFAULT_10 = -32'sd1600054;
localparam signed [31:0] DEFAULT_11 = 32'sd657241;
localparam signed [31:0] DEFAULT_12 = -32'sd1271;
localparam signed [31:0] DEFAULT_13 = -32'sd465;
localparam signed [31:0] DEFAULT_14 = 32'sd1;
localparam signed [31:0] DEFAULT_15 = 32'sd0;
