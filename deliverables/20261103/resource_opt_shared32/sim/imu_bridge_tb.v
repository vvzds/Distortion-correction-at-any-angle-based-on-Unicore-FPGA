`timescale 1ns/1ps
module imu_bridge_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,rx=1,frame=0;
    reg [2:0] baud=1;
    wire [383:0] snapshot;
    imu_bridge #(.CLOCK_HZ(1152000)) dut(clk,rst_n,rx,baud,frame,snapshot);
    task send_byte;
        input [7:0] b;integer i;
        begin
            @(negedge clk);rx=0;repeat(10) @(negedge clk);
            for(i=0;i<8;i=i+1) begin rx=b[i];repeat(10) @(negedge clk);end
            rx=1;repeat(10) @(negedge clk);
        end
    endtask
    task sample;
        input [7:0] kind;input bad;
        reg [7:0] sum;integer i;
        begin
            sum=8'h55+kind;send_byte(8'h55);send_byte(kind);
            for(i=0;i<8;i=i+1) begin send_byte(i+1);sum=sum+i+1;end
            send_byte(sum^{7'd0,bad});repeat(10) @(negedge clk);
        end
    endtask
    reg [31:0] timestamp;
    initial begin
        repeat(5) @(negedge clk);rst_n=1;repeat(5) @(negedge clk);
        frame=1;@(negedge clk);frame=0;
        sample(8'h52,0);timestamp=snapshot[159:128];
        if(snapshot[223:160]!=64'h0807060504030201 || snapshot[319:256]!=0 ||
           snapshot[375:352]!=0 || snapshot[377:376]!=1 || timestamp==0 ||
           snapshot[127:96]!=1 || snapshot[95:64]==0)
            $fatal(1,"Gyro snapshot/time");
        sample(8'h53,1);
        if(snapshot[351:320]!=1 || snapshot[375:352]!=0 || snapshot[377:376]!=1)
            $fatal(1,"Checksum rejection");
        send_byte(8'h01);send_byte(8'h55);send_byte(8'h20);
        sample(8'h53,0);
        if(snapshot[319:256]!=64'h0807060504030201 || snapshot[377:376]!=3 ||
           snapshot[255:224]<=timestamp || snapshot[375:352]!=1)
            $fatal(1,"Resync/angle");
        baud=0;repeat(5) @(negedge clk);
        if(snapshot[377:376]!=0 || snapshot[383:381]!=0) $fatal(1,"Baud invalidation");
        $display("PASS IMU checksum, timestamps, frame event, resync and baud invalidation");$finish;
    end
    initial begin #2000000;$fatal(1,"Timeout");end
endmodule
