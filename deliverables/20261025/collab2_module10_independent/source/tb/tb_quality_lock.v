`timescale 1ns/1ps
module tb_quality_lock;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,init_done=1,start=0;reg[1:0]cmd=0;
    wire busy,done,error,locked,recovery,valid;
    wire[119:0]snapshot;
    wire req,rd;reg ready=1,rsp=0,rerr=0;reg[7:0]rdata=0;
    wire[15:0]addr;wire[7:0]wdata;
    reg[7:0]mem[0:65535];
    integer errors=0,i,ops=0,fail_at=-1,delay_count=0,delay_value=2;
    reg pending=0,hold_responses=0;
    reg[15:0]saved_addr;reg saved_rd;reg[7:0]saved_data;
    ov5640_quality_lock #(.TIMEOUT_CYCLES(1200)) dut(
      .clk(clk),.rst_n(rst_n),.init_done(init_done),.start(start),.cmd(cmd),
      .busy(busy),.done(done),.error(error),.locked(locked),.recovery_required(recovery),
      .snapshot_valid(valid),.snapshot(snapshot),.req_valid(req),.req_ready(ready),
      .req_read(rd),.req_addr(addr),.req_wdata(wdata),.rsp_valid(rsp),.rsp_error(rerr),.rsp_rdata(rdata));
    always @(negedge clk) begin
        rsp=0;rerr=0;
        if(!rst_n) begin pending=0;delay_count=0;end
        else if(req && ready && !pending) begin
            pending=1;saved_addr=addr;saved_rd=rd;saved_data=wdata;delay_count=delay_value;
        end else if(pending && !hold_responses) begin
            if(delay_count>0) delay_count=delay_count-1;
            else begin
                rsp=1;ops=ops+1;rerr=(ops==fail_at);
                if(!rerr) begin if(saved_rd) rdata=mem[saved_addr];else mem[saved_addr]=saved_data;end
                pending=0;
            end
        end
    end
    task check;
      input pass;input[8*100-1:0]message;
      begin if(!pass) begin errors=errors+1;$display("FAIL: %0s",message);end end
    endtask
    task reset_all;
      begin
        @(posedge clk);#1;rst_n=0;start=0;ready=1;hold_responses=0;
        repeat(3)@(posedge clk);#1;rst_n=1;ops=0;fail_at=-1;
        for(i=0;i<65536;i=i+1) mem[i]=8'h55;
        mem[16'h3503]=8'hA0;mem[16'h3406]=8'hc0;
      end
    endtask
    task launch;
      input[1:0]c;
      begin @(negedge clk);cmd=c;start=1;@(negedge clk);start=0;wait(done);#1;end
    endtask
    initial begin
        reset_all;init_done=0;launch(0);check(error && ops==0,"Reject before initialization");
        init_done=1;launch(0);check(!error && locked && valid && ops==38,"Lock completes and verifies 38 transactions");
        check(mem[16'h3503]==8'ha3 && mem[16'h3406]==8'hc1,"Preserve reserved bits");
        check(snapshot[7:0]==8'ha3 && snapshot[15:8]==8'hc1,"Snapshot mode bytes");
        launch(2);check(!error && locked,"Verify stable values");
        launch(0);check(error && locked,"Reject duplicate lock without losing recovery data");
        launch(1);check(!error && !locked && !valid && !recovery,"Restore completed");
        check(mem[16'h3503]==8'ha0 && mem[16'h3406]==8'hc0,"Restore exact prior modes");
        launch(1);check(error,"Restore requires saved original");
        reset_all;launch(0);mem[16'h3501]=8'h56;launch(2);
        check(error && !locked && recovery && !valid,"Drift invalidates snapshot");
        launch(1);check(!error && !recovery,"Recover after drift");
        // 每个锁定事务分别注入NACK，不能假成功；保留可恢复状态。
        for(i=1;i<=38;i=i+1) begin : inject
            integer n;
            n=i;
            @(negedge clk);rst_n=0;repeat(2)@(posedge clk);#1;rst_n=1;
            mem[16'h3503]=8'ha0;mem[16'h3406]=8'hc0;ops=0;fail_at=n;
            launch(0);check(error && !locked && !valid,"NACK must fail closed");
            if(recovery) begin fail_at=-1;launch(1);check(!error,"Restore partial transaction");end
        end
        reset_all;hold_responses=1;launch(0);check(error && !locked,"Response timeout");
        reset_all;ready=0;launch(0);check(error && ops==0,"Request backpressure timeout");
        reset_all;delay_value=9;launch(0);check(!error && valid,"Delayed bus responses");
        launch(3);check(error,"Reject reserved command");
        if(errors==0)$display("=== ALL TESTS PASSED (err=0) ===");
        else $display("TESTS FAILED errors=%0d",errors);
        $finish;
    end
    initial begin #10000000;$display("TEST TIMEOUT");$finish;end
endmodule
