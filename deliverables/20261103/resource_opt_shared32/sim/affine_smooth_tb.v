`timescale 1ns/1ps
module affine_smooth_tb;
    reg clk=0; always #4 clk=~clk;
    reg rst_n=0;
    reg [511:0] cfg;
    wire [511:0] published_cfg;
    wire busy;
    tile_engine dut(.clk(clk),.rst_n(rst_n),.frame_update(1'b0),.cfg(cfg),.config_pending(1'b0),
        .busy(busy),.src_gnt(1'b0),.src_slot(2'd0),.rd_gnt(1'b0),.rd_valid(1'b0),.rd_last(1'b0),
        .rd_data(256'd0),.slot_gnt(1'b0),.slot(3'd4),.wr_gnt(1'b0),.published(1'b0),
        .published_cfg(published_cfg),.src_req(),.src_rel(),.rd_req(),.rd_addr(),.rd_len(),
        .slot_req(),.wr_req(),.wr_addr(),.wr_data(),.commit(),.frame_count(),.last_cycles(),
        .last_rd_wait(),.last_wr_wait(),.last_read_beats(),.last_invalid(),.overflow_tiles(),
        .protocol_fault(),.gamma_mode());
    `include "source/rtl/default_config.vh"
    task next_frame;
        begin
            @(negedge clk);dut.fs=0;dut.pending=1;
            @(negedge clk);
        end
    endtask
    integer i;
    reg signed [31:0] previous,actual;
    initial begin
        cfg={DEFAULT_15,DEFAULT_14,DEFAULT_13,DEFAULT_12,DEFAULT_11,DEFAULT_10,
             DEFAULT_9,DEFAULT_8,DEFAULT_7,DEFAULT_6,DEFAULT_5,DEFAULT_4,
             DEFAULT_3,DEFAULT_2,DEFAULT_1,DEFAULT_0};
        repeat(6) @(negedge clk);rst_n=1;
        next_frame();
        if(dut.frame_cfg!==cfg) $fatal(1,"First frame must be exact");
        dut.frame_count=1;
        cfg[15*32+17]=1;
        cfg[2*32+:32]=$signed(cfg[2*32+:32])+1024;
        previous=$signed(dut.frame_cfg[2*32+:32]);
        for(i=0;i<12;i=i+1) begin
            next_frame();actual=$signed(dut.frame_cfg[2*32+:32]);
            if(actual<=previous && actual!=$signed(cfg[2*32+:32])) $fatal(1,"Progress stalled");
            if(actual>$signed(cfg[2*32+:32])) $fatal(1,"Overshoot");
            previous=actual;
        end
        if(actual!=$signed(cfg[2*32+:32])) $fatal(1,"Fixed-point convergence");
        cfg[0+:32]=$signed(cfg[0+:32])-101;
        next_frame();
        if($signed(dut.frame_cfg[0+:32])!=$signed(cfg[0+:32])+50) $fatal(1,"Negative rounding");
        cfg[15*32+17]=0;
        next_frame();
        if(dut.frame_cfg!==cfg) $fatal(1,"OFF must restore exactly");
        // A legacy client's marker flag must never affect any video pixel.
        cfg[15*32+:32]=32'h0001beef;
        next_frame();
        force dut.enhanced_pixel=16'h52a9;
        for(i=0;i<2048;i=i+1) begin
            force dut.render_received=i;
            #1;
            if(dut.final_pixel!==16'h52a9) $fatal(1,"Diagnostic pixel leaked");
        end
        release dut.render_received;release dut.enhanced_pixel;
        $display("PASS frame-by-frame affine progression, convergence, exact OFF, no marker pixels");$finish;
    end
    initial begin #100000;$fatal(1,"Timeout");end
endmodule
