`timescale 1ns/1ps
module bno085_bridge_tb;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,miso=0,int_n=1,restart=0,frame=0;
    reg [2:0] mode=0;
    wire sck,mosi,cs_n,sensor_rst_n,wake_n;
    wire [383:0] snapshot,diagnostics;
    bno085_bridge #(.CLOCK_HZ(1000000),.SPI_HALF_DIV(8)) dut(
        clk,rst_n,miso,int_n,sck,mosi,cs_n,sensor_rst_n,wake_n,
        mode,restart,frame,snapshot,diagnostics);
    reg [7:0] outgoing[0:1023],received[0:1023];
    integer tx_bit=0,rx_bit=0,out_length=0,i;
    integer sets=0,gets=0,products=0;
    reg [7:0] incoming_shift=0;
    reg [7:0] seq=0;
    task clear_out;
        begin for(i=0;i<1024;i=i+1) outgoing[i]=0;out_length=0;end
    endtask
    task header;
        input integer len;input [7:0] channel;
        begin
            clear_out();out_length=len;outgoing[0]=len%256;outgoing[1]=len/256;
            outgoing[2]=channel;outgoing[3]=seq;seq=seq+1;
        end
    endtask
    always @(negedge cs_n) begin
        tx_bit=0;rx_bit=0;incoming_shift=0;
        for(integer j=0;j<1024;j=j+1) received[j]=0;
        int_n=1;
    end
    always @(negedge sck) if(!cs_n) begin
        miso=(tx_bit/8<out_length)?outgoing[tx_bit/8][7-tx_bit%8]:0;
        tx_bit=tx_bit+1;
    end
    always @(posedge sck) if(!cs_n) begin
        incoming_shift={incoming_shift[6:0],mosi};
        if(rx_bit%8==7) received[rx_bit/8]=incoming_shift;
        rx_bit=rx_bit+1;
    end
    always @(negedge wake_n) begin #40;if(sensor_rst_n && cs_n) int_n=0;end
    always @(posedge sensor_rst_n) begin
        #5000;header(5,1);outgoing[4]=1;int_n=0;
    end
    always @(posedge cs_n) if(sensor_rst_n && rx_bit>=32) begin
        clear_out();
        if(received[0]!=0) begin
            if(received[2]!=2) $fatal(1,"Host sent wrong channel");
            if(received[4]==8'hf9) begin
                products=products+1;header(20,2);outgoing[4]=8'hf8;
                outgoing[6]=3;outgoing[7]=2;outgoing[8]=8'h34;outgoing[9]=8'h12;
                outgoing[12]=8'h78;outgoing[13]=8'h56;
            end else if(received[4]==8'hfd) begin
                sets=sets+1;
                if(received[0]!=21 || received[9]!=8'h88 || received[10]!=8'h13 || received[6]!=0)
                    $fatal(1,"SET Feature encoding");
                header(21,2);outgoing[4]=8'hfc;outgoing[5]=received[5];
                outgoing[9]=8'h88;outgoing[10]=8'h13;
            end else if(received[4]==8'hfe) begin
                gets=gets+1;header(21,2);outgoing[4]=8'hfc;outgoing[5]=received[5];
                outgoing[9]=8'h88;outgoing[10]=8'h13;
            end else $fatal(1,"Unexpected outgoing command");
        end
        #1000;if(out_length!=0) int_n=0;
    end
    task wait_idle;
        begin wait(dut.state==2 && cs_n && int_n);repeat(100) @(negedge clk);end
    endtask
    task data_packet;
        begin
            header(31,3);
            outgoing[4]=8'hfb;outgoing[5]=10; // sample = irq -1000us
            outgoing[9]=2;outgoing[10]=1;outgoing[12]=2; // gyro report delay 2 => +200us
            outgoing[13]=0;outgoing[14]=2; // gyro X=512 => 1rad/s
            outgoing[19]=mode==1?8'h29:8'h08;outgoing[20]=1;outgoing[22]=3; // quat delay3 => +300us
            outgoing[29]=0;outgoing[30]=8'h40; // real=16384
            int_n=0;
        end
    endtask
    reg [31:0] before_errors,first_pose,first_generation;integer previous_sets,previous_gets;
    initial begin
        clear_out();repeat(8) @(negedge clk);rst_n=1;
        wait(sets==2 && gets==2 && products==1);wait_idle();
        if(diagnostics[287:256]!=5000 || diagnostics[319:288]!=5000 || diagnostics[119:112]==0)
            $fatal(1,"Feature/product readback");
        frame=1;@(negedge clk);frame=0;
        data_packet();wait(snapshot[377:376]==3);wait_idle();
        if(snapshot[319:256]!=64'h4000000000000000 || snapshot[207:160]!=48'd512)
            $fatal(1,"Quaternion/gyro little endian");
        if(snapshot[255:224]-snapshot[159:128]!=100 || snapshot[375:352]!=1 || snapshot[127:96]!=1)
            $fatal(1,"SH2 timestamp/delay/packet count");
        first_pose=snapshot[255:224];before_errors=snapshot[351:320];
        header(10,3);outgoing[4]=8'h08;int_n=0;wait(!cs_n);wait_idle();
        if(snapshot[351:320]<=before_errors || snapshot[255:224]!=first_pose)
            $fatal(1,"Truncated quaternion published");
        before_errors=snapshot[351:320];
        header(8,3);outgoing[1]=8'h80;int_n=0;wait(!cs_n);wait_idle();
        if(snapshot[351:320]<=before_errors || snapshot[255:224]!=first_pose)
            $fatal(1,"Continuation not rejected");
        header(530,0);int_n=0;wait(!cs_n);wait_idle();
        if(diagnostics[223:192]==0 || snapshot[255:224]!=first_pose)
            $fatal(1,"Oversize drain");
        // Mode switch must reset old validity and request ARVR report id.
        previous_sets=sets;previous_gets=gets;mode=1;
        wait(sets==previous_sets+2 && gets==previous_gets+2);wait_idle();
        if(diagnostics[103:96]!=8'h29 || snapshot[377:376]!=0) $fatal(1,"ARVR mode configuration");
        data_packet();wait(snapshot[377:376]==3);wait_idle();
        previous_sets=sets;previous_gets=gets;mode=2;
        wait(sets==previous_sets+1 && gets==previous_gets+1);wait_idle();
        header(18,5);outgoing[10]=0;outgoing[11]=8'h40;
        outgoing[12]=0;outgoing[13]=4; // gyro X Q10 = 1rad/s
        int_n=0;wait(snapshot[377:376]==3);wait_idle();
        if(snapshot[319:256]!=64'h4000000000000000 || snapshot[207:160]!=1024 ||
           snapshot[383:381]!=2 || snapshot[255:224]!=snapshot[159:128])
            $fatal(1,"GIRV packed quaternion/gyro");
        first_generation=snapshot[223:208];
        restart=1;wait(!sensor_rst_n);wait(sensor_rst_n);
        if(snapshot[377:376]!=0 || snapshot[223:208]<=first_generation)
            $fatal(1,"Reset generation/validity");
        $display("PASS BNO SPI startup, features, SH2 times, truncation/continuation/oversize, ARVR/GIRV, reset");$finish;
    end
    initial begin #30000000;$fatal(1,"Timeout state=%d init=%d sets=%d gets=%d",dut.state,dut.init_step,sets,gets);end
endmodule
