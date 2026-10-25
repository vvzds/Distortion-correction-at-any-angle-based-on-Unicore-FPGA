`timescale 1ns/1ps
module tb_quality_control;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,start=0;reg[1:0]cmd=0;
    wire busy,done,error,locked,recovery,valid;
    wire[119:0]snapshot;
    tri1 scl,sda;
    wire scl_low,sda_low;reg slave_low=0,stretch=0;
    assign scl=(scl_low || stretch)?1'b0:1'bz;
    assign sda=(sda_low || slave_low)?1'b0:1'bz;
    reg[7:0]mem[0:65535];
    integer errors=0,i,ops=0;
    reg[7:0]b,hi,lo,d;
    ov5640_quality_control #(.HALF_CYCLES(6),.BUS_TIMEOUT(6000),.LOCK_TIMEOUT(300000)) dut(
      .clk(clk),.rst_n(rst_n),.init_done(1'b1),.start(start),.cmd(cmd),
      .busy(busy),.done(done),.error(error),.locked(locked),.recovery_required(recovery),
      .snapshot_valid(valid),.snapshot(snapshot),.scl_in(scl),.sda_in(sda),
      .scl_low(scl_low),.sda_low(sda_low));
    task check;
      input pass;input[8*100-1:0]message;
      begin if(!pass)begin errors=errors+1;$display("FAIL: %0s",message);end end
    endtask
    task wait_start;
      begin : ws forever begin @(negedge sda);if(scl===1'b1)disable ws;end end
    endtask
    task wait_stop;
      begin : wp forever begin @(posedge sda);if(scl===1'b1)disable wp;end end
    endtask
    task receive;
      output[7:0]v;integer j;
      begin for(j=7;j>=0;j=j-1)begin @(posedge scl);v[j]=sda;end end
    endtask
    task ack;
      begin @(negedge scl);#1;slave_low=1;@(posedge scl);@(negedge scl);#1;slave_low=0;end
    endtask
    task transmit;
      input[7:0]v;integer j;
      begin
        for(j=7;j>=0;j=j-1)begin slave_low=~v[j];@(posedge scl);@(negedge scl);#1;end
        slave_low=0;@(posedge scl);check(sda===1'b1,"Master NACK after byte");@(negedge scl);
      end
    endtask
    initial forever begin
        wait_start;ops=ops+1;
        receive(b);check(b==8'h78,"Address write phase");ack;
        receive(hi);ack;receive(lo);ack;
        // 只从线上判断接下来是重复起始还是写数据，不窥探DUT请求。
        fork : next_phase
            begin
                wait_start;disable next_phase;
            end
            begin
                @(posedge scl);#2;
                // 重复起始的第一个上升沿SDA为1，稍后下降则是起始。
                @(negedge scl);disable next_phase;
            end
        join
        // 写事务已送出第一位，重复起始事务此时SCL仍高。
        if(scl===1'b1)begin
            receive(b);check(b==8'h79,"Read phase device address");ack;
            transmit(mem[{hi,lo}]);
        end else begin
            // 上面的探测已消费第一位的SCL高脉冲，先取其数据。
            // 第一位在下降沿之后仍保持，后续7位继续读取。
            d[7]=sda;
            for(i=6;i>=0;i=i-1)begin @(posedge scl);d[i]=sda;end
            ack;mem[{hi,lo}]=d;
        end
        wait_stop;
    end
    task launch;
      input[1:0]c;
      begin @(negedge clk);cmd=c;start=1;@(negedge clk);start=0;wait(done);#1;end
    endtask
    integer k;
    initial begin
        for(k=0;k<65536;k=k+1)mem[k]=8'h24;
        mem[16'h3503]=8'ha0;mem[16'h3406]=8'hc0;
        repeat(3)@(posedge clk);#1;rst_n=1;
        launch(0);check(!error && locked && valid && ops==38,"End to end lock verified on SCCB lines");
        check(mem[16'h3503]==8'ha3 && mem[16'h3406]==8'hc1,"Manual mode applied");
        check(snapshot[23:16]==8'h24,"Snapshot exposure read from model");
        launch(2);check(!error && valid,"End to end stability readback");
        mem[16'h3401]=8'h25;launch(2);check(error && recovery,"End to end changed WB detected");
        launch(1);check(!error && !locked && !recovery,"End to end restore");
        check(mem[16'h3503]==8'ha0 && mem[16'h3406]==8'hc0,"Original control mode restored");
        if(errors==0)$display("=== ALL TESTS PASSED (err=0) ===");
        else $display("TESTS FAILED errors=%0d",errors);
        $finish;
    end
    initial begin #10000000;$display("TEST TIMEOUT");$finish;end
endmodule
