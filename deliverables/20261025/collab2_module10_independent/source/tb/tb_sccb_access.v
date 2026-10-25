`timescale 1ns/1ps
module tb_sccb_access;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,req=0,rd=0;
    reg[15:0]addr=0;reg[7:0]data=0;
    wire ready,rsp,err;wire[7:0]value;
    wire scl_low,sda_low;
    tri1 scl,sda;
    reg slave_low=0,stretch=0,enabled=1;
    integer errors=0,nack_byte=-1,byte_count=0,transactions=0;
    reg[7:0]mem[0:65535];reg[7:0]b,hi,lo,wr;
    assign scl=(scl_low || stretch)?1'b0:1'bz;
    assign sda=(sda_low || slave_low)?1'b0:1'bz;
    ov5640_sccb_access #(.HALF_CYCLES(6),.TIMEOUT_CYCLES(5000)) dut(
      .clk(clk),.rst_n(rst_n),.req_valid(req),.req_ready(ready),.req_read(rd),
      .req_addr(addr),.req_wdata(data),.rsp_valid(rsp),.rsp_error(err),.rsp_rdata(value),
      .scl_in(scl),.sda_in(sda),.scl_low(scl_low),.sda_low(sda_low));
    task check;
      input pass;input[8*100-1:0]message;
      begin if(!pass) begin errors=errors+1;$display("FAIL: %0s",message);end end
    endtask
    task wait_start;
      begin : wait_s
        forever begin @(negedge sda);if(scl===1'b1)disable wait_s;end
      end
    endtask
    task wait_stop;
      begin : wait_p
        forever begin @(posedge sda);if(scl===1'b1)disable wait_p;end
      end
    endtask
    task receive;
      output[7:0]v;integer j;
      begin for(j=7;j>=0;j=j-1)begin @(posedge scl);v[j]=sda;end end
    endtask
    task ack;
      begin
        @(negedge scl);#1;slave_low=(byte_count!=nack_byte);byte_count=byte_count+1;
        @(posedge scl);@(negedge scl);#1;slave_low=0;
      end
    endtask
    task transmit;
      input[7:0]v;integer j;
      begin
        for(j=7;j>=0;j=j-1)begin slave_low=~v[j];@(posedge scl);@(negedge scl);#1;end
        slave_low=0;@(posedge scl);check(sda===1'b1,"Final read byte must be NACKed");@(negedge scl);
      end
    endtask
    initial forever begin : slave
        wait_start;
        if(enabled) begin : packet
            byte_count=0;transactions=transactions+1;
            receive(b);check(b==8'h78,"Write device address 0x78");ack;
            if(nack_byte==0)begin wait_stop;disable packet;end
            receive(hi);ack;if(nack_byte==1)begin wait_stop;disable packet;end
            receive(lo);ack;if(nack_byte==2)begin wait_stop;disable packet;end
            if(rd)begin
                wait_start;receive(b);check(b==8'h79,"Repeated-start read address 0x79");ack;
                if(nack_byte==3)begin wait_stop;disable packet;end
                transmit(mem[{hi,lo}]);
            end else begin
                receive(wr);ack;
                if(nack_byte!=3)mem[{hi,lo}]=wr;
            end
            wait_stop;
        end
    end
    task transact;
      input r;input[15:0]a;input[7:0]d;
      begin
        wait(ready);@(negedge clk);rd=r;addr=a;data=d;req=1;
        @(negedge clk);req=0;wait(rsp);#1;
      end
    endtask
    integer i;
    initial begin
        for(i=0;i<65536;i=i+1)mem[i]=0;
        repeat(3)@(posedge clk);#1;rst_n=1;
        transact(0,16'h3503,8'ha3);check(!err && mem[16'h3503]==8'ha3,"Register write");
        transact(1,16'h3503,0);check(!err && value==8'ha3,"Register repeated-start read");
        for(i=0;i<16;i=i+1)begin
            transact(0,16'h3400+i,i*17);check(!err,"Write data pattern");
            transact(1,16'h3400+i,0);check(!err && value==i*17,"Read data pattern");
        end
        for(i=0;i<4;i=i+1)begin
            nack_byte=i;transact(0,16'h1234,8'hbc);check(err,"NACK reported");
            transact(1,16'h1234,0);check(err,"Read transaction NACK reported");
        end
        nack_byte=-1;
        fork
            begin transact(1,16'h3503,0);check(!err && value==8'ha3,"Clock stretching");end
            begin @(negedge scl);stretch=1;repeat(30)@(posedge clk);#1;stretch=0;end
        join
        stretch=1;transact(1,16'h3503,0);check(err && !scl_low && !sda_low,"Stuck SCL timeout releases outputs");
        stretch=0;repeat(20)@(posedge clk);
        transact(1,16'h3503,0);check(!err && value==8'ha3,"Next request after timeout");
        if(errors==0)$display("=== ALL TESTS PASSED (err=0) ===");
        else $display("TESTS FAILED errors=%0d",errors);
        $finish;
    end
    initial begin #10000000;$display("TEST TIMEOUT");$finish;end
endmodule
