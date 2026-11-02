`timescale 1ns/1ps
module frame_ownership_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,wr_start=0,wr_complete=0,hold_req=0,release_src=0;
    wire [1:0] wr_bank,raw_read,wcnt,held_slot;
    wire update,held,raw_valid;
    frame_bank_ctrl #(.CORR_ENABLE(1)) source_banks(clk,rst_n,wr_start,wr_complete,1'b0,
        wr_bank,raw_read,wcnt,update,hold_req,held,held_slot,release_src,raw_valid);
    reg rd_start=0,slot_req=0,writer_idle=1,publish=0;
    wire granted,display_valid;wire [2:0] target_slot;wire [1:0] display_bank;
    corr_slot_ctrl targets(clk,rst_n,rd_start,slot_req,writer_idle,publish,
                           granted,target_slot,display_bank,display_valid);
    integer n,phase=0,age=0,allocations=0,holds=0;
    reg [1:0] locked_src,last_display,last_target;
    reg was_held=0,was_display_valid=0,last_rd_start=0;
    reg [31:0] random_state=32'h10203055;
    always @(posedge clk) if(rst_n) begin
        if(held && wr_start && source_banks.next_bank==held_slot)
            $fatal(1,"Camera selected held source slot");
        if(granted) begin
            allocations=allocations+1;last_target=target_slot[1:0];
            if(target_slot[2]!=1) $fatal(1,"Target not in corrected partition");
            if(display_valid && target_slot[1:0]==display_bank) $fatal(1,"Writing display slot");
            if(targets.latest_valid && target_slot[1:0]==targets.latest_bank)
                $fatal(1,"Writing newest published slot");
        end
        if(held && !was_held) begin locked_src=held_slot;holds=holds+1;end
        if(held && was_held && held_slot!=locked_src) $fatal(1,"Source lock changed");
        if(was_display_valid && !last_rd_start && display_bank!=last_display)
            $fatal(1,"Display slot changed outside vertical boundary");
        if(targets.active && targets.wr_bank!=last_target) $fatal(1,"Target lock changed");
        last_display=display_bank;was_display_valid=display_valid;
        last_rd_start=rd_start;was_held=held;
    end
    initial begin
        repeat(5) @(negedge clk);rst_n=1;
        for(n=0;n<20000;n=n+1) begin
            @(negedge clk);
            random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
            wr_complete=(n%47==20);wr_start=(n%47==21);
            hold_req=!held && n%7<4;release_src=held && n%223==0;
            rd_start=n%37==0;
            slot_req=!targets.active;publish=0;
            if(targets.active) begin
                age=age+1;
                if(age>=3+random_state[4:0])begin publish=1;age=0;end
            end else age=0;
        end
        @(negedge clk);
        if(allocations<500 || holds<50) $fatal(1,"Insufficient exercised allocations/holds");
        $display("PASS frame ownership allocations=%0d source_holds=%0d",allocations,holds);$finish;
    end
endmodule
