`timescale 1ns/1ps
// Exact signed 32x32 product, II=1, four register stages. Explicit 16-bit
// partial products prevent the vendor mapper from building a long unregistered
// DSP cascade. Register every accumulation boundary; no truncation is added.
module mul32_pipe #(parameter EXTRA_FINAL_PIPE=0)(input wire clk,
    input wire signed [31:0] a,b,
    output reg signed [63:0] product
);
    reg signed [33:0] ll;
    reg signed [32:0] lh,hl;
    reg signed [31:0] hh;
    reg signed [33:0] middle,ll_d;
    reg signed [31:0] hh_d;
    reg signed [63:0] low_middle,high_part;
    reg [32:0] low_sum;
    reg [31:0] high_sum;
    always @(posedge clk) begin
        ll<=$signed({1'b0,a[15:0]})*$signed({1'b0,b[15:0]});
        lh<=$signed({1'b0,a[15:0]})*$signed(b[31:16]);
        hl<=$signed(a[31:16])*$signed({1'b0,b[15:0]});
        hh<=$signed(a[31:16])*$signed(b[31:16]);
        middle<=$signed({lh[32],lh})+$signed({hl[32],hl});ll_d<=ll;hh_d<=hh;
        low_middle<=$signed(ll_d)+($signed({{30{middle[33]}},middle})<<<16);
        high_part<=$signed({{32{hh_d[31]}},hh_d})<<<32;
    end

    generate if(EXTRA_FINAL_PIPE) begin : g_split_final_sum
        always @(posedge clk) begin
            low_sum<={1'b0,low_middle[31:0]}+{1'b0,high_part[31:0]};
            high_sum<=low_middle[63:32]+high_part[63:32];
            product<={high_sum+{31'd0,low_sum[32]},low_sum[31:0]};
        end
    end else begin : g_single_final_sum
        always @(posedge clk) begin
            product<=low_middle+high_part;
        end
    end endgenerate
endmodule
