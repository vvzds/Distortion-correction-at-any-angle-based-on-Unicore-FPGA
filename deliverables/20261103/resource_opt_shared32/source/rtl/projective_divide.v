`timescale 1ns/1ps
// Pipelined inverse-projective divide for normalized Q20 camera rays.
// g0/g1 are Q14 denominator slopes; initiation interval is one pixel/clock.
module projective_divide(
    input wire clk, rst_n,
    input wire in_valid,
    input wire signed [23:0] x, y,
    input wire signed [15:0] g0, g1,
    output reg out_valid, out_ok,
    output reg signed [23:0] out_x, out_y
);
    function signed [23:0] reciprocal_seed;
        input [3:0] index;
        begin
            case(index)
                0: reciprocal_seed=24'sd1973790;
                1: reciprocal_seed=24'sd1766023;
                2: reciprocal_seed=24'sd1597830;
                3: reciprocal_seed=24'sd1458888;
                4: reciprocal_seed=24'sd1342177;
                5: reciprocal_seed=24'sd1242757;
                6: reciprocal_seed=24'sd1157049;
                7: reciprocal_seed=24'sd1082401;
                8: reciprocal_seed=24'sd1016801;
                9: reciprocal_seed=24'sd958698;
                10: reciprocal_seed=24'sd906877;
                11: reciprocal_seed=24'sd860370;
                12: reciprocal_seed=24'sd818401;
                13: reciprocal_seed=24'sd780336;
                14: reciprocal_seed=24'sd745654;
                default: reciprocal_seed=24'sd713924;
            endcase
        end
    endfunction

    reg signed [39:0] gx0,gy0;
    reg signed [23:0] x0,y0;
    reg signed [23:0] den1,x1,y1;
    reg ok1;
    wire signed [41:0] sum0=$signed({gx0[39],gx0})+$signed({gy0[39],gy0});
    wire signed [41:0] den_wide=42'sd1048576+(sum0>>>14);
    wire den_in_range=den_wide>=42'sd524288 && den_wide<=42'sd1572864;
    wire [23:0] den_bias=den1-24'd524288;
    wire [3:0] seed_index=den_bias[19:16];

    reg signed [23:0] seed2,den2,x2,y2;
    reg signed [47:0] dseed3;
    reg signed [23:0] seed3,den3,x3,y3;
    reg signed [23:0] correction4,seed4,den4,x4,y4;
    reg signed [23:0] reciprocal5,den5,x5,y5;
    reg signed [47:0] dreciprocal6;
    reg signed [23:0] reciprocal6,x6,y6;
    reg signed [23:0] correction7,reciprocal7,x7,y7;
    reg signed [23:0] reciprocal8,x8,y8;
    reg signed [47:0] xreciprocal9,yreciprocal9;
    wire signed [47:0] result_x_wide=xreciprocal9>>>20;
    wire signed [47:0] result_y_wide=yreciprocal9>>>20;
    reg [9:0] valid_pipe;
    reg [7:0] ok_pipe;
    integer i;

    always @(posedge clk) begin
        gx0 <= $signed({{24{g0[15]}},g0})*$signed({{16{x[23]}},x});
        gy0 <= $signed({{24{g1[15]}},g1})*$signed({{16{y[23]}},y});
        x0 <= x;
        y0 <= y;

        den1 <= den_wide[23:0];
        x1 <= x0;
        y1 <= y0;
        ok1 <= den_in_range;

        seed2 <= reciprocal_seed(seed_index);
        den2 <= den1;
        x2 <= x1;
        y2 <= y1;

        dseed3 <= $signed({{24{den2[23]}},den2})*
                  $signed({{24{seed2[23]}},seed2});
        seed3 <= seed2;
        den3 <= den2;
        x3 <= x2;
        y3 <= y2;

        correction4 <= 24'sd2097152-$signed(dseed3>>>20);
        seed4 <= seed3;
        den4 <= den3;
        x4 <= x3;
        y4 <= y3;

        reciprocal5 <= ($signed({{24{seed4[23]}},seed4})*
                        $signed({{24{correction4[23]}},correction4}))>>>20;
        den5 <= den4;
        x5 <= x4;
        y5 <= y4;

        dreciprocal6 <= $signed({{24{den5[23]}},den5})*
                        $signed({{24{reciprocal5[23]}},reciprocal5});
        reciprocal6 <= reciprocal5;
        x6 <= x5;
        y6 <= y5;

        correction7 <= 24'sd2097152-$signed(dreciprocal6>>>20);
        reciprocal7 <= reciprocal6;
        x7 <= x6;
        y7 <= y6;

        reciprocal8 <= ($signed({{24{reciprocal7[23]}},reciprocal7})*
                        $signed({{24{correction7[23]}},correction7}))>>>20;
        x8 <= x7;
        y8 <= y7;

        xreciprocal9 <= $signed({{24{x8[23]}},x8})*
                        $signed({{24{reciprocal8[23]}},reciprocal8});
        yreciprocal9 <= $signed({{24{y8[23]}},y8})*
                        $signed({{24{reciprocal8[23]}},reciprocal8});

        out_x <= xreciprocal9>>>20;
        out_y <= yreciprocal9>>>20;
    end

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            valid_pipe<=0;
            ok_pipe<=0;
            out_valid<=0;
            out_ok<=0;
        end else begin
            valid_pipe<={valid_pipe[8:0],in_valid};
            ok_pipe<={ok_pipe[6:0],ok1};
            out_valid<=valid_pipe[9];
            out_ok<=valid_pipe[9] && ok_pipe[7] &&
                    result_x_wide>=-48'sd1572864 && result_x_wide<=48'sd1572864 &&
                    result_y_wide>=-48'sd1572864 && result_y_wide<=48'sd1572864;
        end
    end
endmodule
