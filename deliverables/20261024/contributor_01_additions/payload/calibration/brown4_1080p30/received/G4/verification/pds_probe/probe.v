// 用于隔离 PDS 启动问题的单寄存器探针，不属于 core 逻辑。
module probe(input wire clk, input wire a, output reg q);
    always @(posedge clk) q <= a;
endmodule
