`timescale 1ns/1ps

module strip_reorder_rate_tb;
    parameter WIDTH=1920, HEIGHT=1080, STRIP_H=16;
    localparam XW=$clog2(WIDTH), YW=$clog2(HEIGHT+1);
    reg clk=0, rst_n=0, frame_start=0, in_valid=0;
    always #4 clk=~clk;
    wire in_ready, out_valid, sof, eof, input_done, output_done;
    wire [15:0] out_pixel;
    wire [XW-1:0] out_x;
    wire [YW-1:0] out_y;
    integer base=0, col=0, row=0, strip_height=0;
    integer cycles=0, accepted=0, received=0, errors=0;
    wire [15:0] in_pixel=(base+row)*WIDTH+col;

    strip_reorder #(.WIDTH(WIDTH), .HEIGHT(HEIGHT), .STRIP_H(STRIP_H)) dut (
        .clk(clk), .rst_n(rst_n), .i_frame_start(frame_start),
        .i_valid(in_valid), .o_ready(in_ready), .i_pixel(in_pixel),
        .o_valid(out_valid), .i_ready(1'b1), .o_pixel(out_pixel),
        .o_x(out_x), .o_y(out_y), .o_sof(sof), .o_eof(eof),
        .o_input_done(input_done), .o_output_done(output_done)
    );

    always @(posedge clk) begin
        if (rst_n && !frame_start) begin
            cycles=cycles+1;
            if (in_valid && in_ready) begin
                accepted=accepted+1;
                if (row==strip_height-1) begin
                    row<=0;
                    if (col==WIDTH-1) begin
                        col<=0;
                        base<=base+strip_height;
                        strip_height<=
                            (HEIGHT-base-strip_height<STRIP_H)?
                            HEIGHT-base-strip_height:STRIP_H;
                        if (base+strip_height==HEIGHT) in_valid<=0;
                    end else col<=col+1;
                end else row<=row+1;
            end
            if (out_valid) begin
                if (out_pixel !== (received&16'hffff) ||
                    out_x !== received%WIDTH || out_y !== received/WIDTH ||
                    sof !== (received==0) || eof !== (received==WIDTH*HEIGHT-1))
                    errors=errors+1;
                received=received+1;
            end
            if (cycles>WIDTH*HEIGHT*3) $fatal(1,"RATE TIMEOUT accepted=%0d received=%0d",accepted,received);
        end
    end

    initial begin
        repeat (2) @(negedge clk);
        rst_n=1;
        frame_start=1;
        strip_height=(HEIGHT<STRIP_H)?HEIGHT:STRIP_H;
        @(negedge clk);
        frame_start=0;
        in_valid=1;
        wait(output_done);
        @(negedge clk);
        if (accepted!=WIDTH*HEIGHT || received!=WIDTH*HEIGHT || !input_done || errors!=0)
            $fatal(1,"RATE FAIL accepted=%0d received=%0d errors=%0d",accepted,received,errors);
        $display("STRIP RATE PASS pixels=%0d cycles=%0d cpp=%f modeled_fps=%f",
                 received,cycles,cycles*1.0/received,125000000.0/cycles);
        $finish;
    end
endmodule
