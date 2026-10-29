// Select the cache set hash from the output-u direction of the affine map.
// The caller snapshots this value at frame start and clears tags on a change.
module source_hash_mode (
    input wire affine_enable,
    input wire signed [31:0] a11_q16,
    input wire signed [31:0] a21_q16,
    output wire vertical_hash
);
    wire [31:0] abs_a11 = a11_q16[31] ? -a11_q16 : a11_q16;
    wire [31:0] abs_a21 = a21_q16[31] ? -a21_q16 : a21_q16;
    assign vertical_hash = affine_enable &&
                           ({1'b0,abs_a21} > ({1'b0,abs_a11} << 3));
endmodule
