`timescale 1ns/1ps

module strip_reorder_tb;
    parameter WIDTH=7, HEIGHT=5, STRIP_H=2;
    localparam XW=$clog2(WIDTH), YW=$clog2(HEIGHT+1);
    reg clk=0, rst_n=0, frame_start=0, in_valid=0, out_ready=0;
    reg [15:0] in_pixel=0;
    wire in_ready, out_valid, sof, eof, input_done, output_done;
    wire [15:0] out_pixel;
    wire [XW-1:0] out_x;
    wire [YW-1:0] out_y;
    integer cycles=0, received=0, errors=0, offset=0;
    integer base, x, row, strip_height, sent;
    always #4 clk=~clk;

    strip_reorder #(.WIDTH(WIDTH), .HEIGHT(HEIGHT), .STRIP_H(STRIP_H)) dut (
        .clk(clk), .rst_n(rst_n), .i_frame_start(frame_start),
        .i_valid(in_valid), .o_ready(in_ready), .i_pixel(in_pixel),
        .o_valid(out_valid), .i_ready(out_ready), .o_pixel(out_pixel),
        .o_x(out_x), .o_y(out_y), .o_sof(sof), .o_eof(eof),
        .o_input_done(input_done), .o_output_done(output_done)
    );

    always @(posedge clk) begin
        cycles=cycles+1;
        if (rst_n && out_valid && out_ready) begin
            if (out_pixel !== ((offset+received)&16'hffff) ||
                out_x !== received%WIDTH ||
                out_y !== received/WIDTH ||
                sof !== (received==0) ||
                eof !== (received==WIDTH*HEIGHT-1)) begin
                $display("FAIL at %0d: pixel=%0d x=%0d y=%0d sof=%0d eof=%0d",
                         received,out_pixel,out_x,out_y,sof,eof);
                errors=errors+1;
            end
            received=received+1;
        end
    end

    always @(negedge clk) begin
        if (rst_n && !frame_start) out_ready=(cycles%7!=0 && cycles%7!=1);
        else out_ready=0;
    end

    task run_frame;
        input integer value_offset;
        begin
            @(negedge clk);
            frame_start=1;
            in_valid=0;
            offset=value_offset;
            received=0;
            @(negedge clk);
            frame_start=0;
            sent=0;
            for (base=0;base<HEIGHT;base=base+STRIP_H) begin
                strip_height=(HEIGHT-base<STRIP_H)?HEIGHT-base:STRIP_H;
                for (x=0;x<WIDTH;x=x+1) begin
                    for (row=0;row<strip_height;row=row+1) begin
                        @(negedge clk);
                        in_pixel=value_offset+(base+row)*WIDTH+x;
                        in_valid=1;
                        while (!in_ready) @(negedge clk);
                        @(posedge clk);
                        sent=sent+1;
                        @(negedge clk);
                        in_valid=0;
                        if (sent%5==0) @(negedge clk);
                    end
                end
            end
            wait(output_done);
            @(negedge clk);
            if (!input_done || received!=WIDTH*HEIGHT) begin
                $display("FAIL frame completion: input=%0d received=%0d",input_done,received);
                errors=errors+1;
            end
        end
    endtask

    initial begin
        repeat (2) @(negedge clk);
        rst_n=1;
        run_frame(100);
        run_frame(1000);
        if (errors==0) $display("STRIP REORDER PASS width=%0d height=%0d strip=%0d",WIDTH,HEIGHT,STRIP_H);
        else $fatal(1,"STRIP REORDER FAIL errors=%0d",errors);
        $finish;
    end
    initial begin
        #(WIDTH*HEIGHT*160);
        $fatal(1,"STRIP REORDER TIMEOUT sent=%0d received=%0d",sent,received);
    end
endmodule
