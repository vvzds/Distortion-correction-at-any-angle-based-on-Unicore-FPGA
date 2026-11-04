`timescale 1ns/1ps
module host_control_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,rx=1,busy=1;
    wire tx,pending,map_enable,map_update,map_capture_toggle,imu_restart;
    wire [2:0] imu_baud_code;
    wire [1:0] denoise_level,sharpen_level;
    wire quality_update,osd_update,osd_visible,osd_row_valid;
    wire [2:0] osd_row_index;wire [383:0] osd_row_data;
    wire [511:0] cfg;wire [15:0] active_seq;
    wire [31:0] errors,packets;
    reg osd_seen=0;reg [2:0] osd_row_seen=0;reg [383:0] osd_data_seen=0;
    integer map_update_count=0;reg map_update_state=0;
    always @(posedge clk) if(map_update) begin map_update_count<=map_update_count+1;map_update_state<=map_enable;end
    always @(posedge clk) if(dut.osd_row_valid) begin
        osd_seen<=1;osd_row_seen<=dut.osd_row_index;osd_data_seen<=dut.osd_row_data;
    end
    host_control #(.CLOCK_HZ(1152000),.BAUD(115200)) dut(
        .clk(clk),.rst_n(rst_n),.uart_rx(rx),.uart_tx(tx),.busy(busy),
        .imu_snapshot(384'h494d5501),.imu_diagnostics(384'h424e4401),
        .imu_baud_code(imu_baud_code),.imu_restart(imu_restart),
        .imu_map_enable(map_enable),.imu_map_update(map_update),.imu_capture_toggle(map_capture_toggle),
        .denoise_level(denoise_level),.sharpen_level(sharpen_level),
        .quality_update(quality_update),.osd_update(osd_update),
        .osd_row_valid(osd_row_valid),.osd_visible(osd_visible),
        .osd_row_index(osd_row_index),.osd_row_data(osd_row_data),
        .telemetry(256'h0000000a00000009000000080000000700000006000000050000000400000003),
        .published_cfg(512'h0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef),
        .cfg(cfg),.pending(pending),.active_sequence(active_seq),.rx_errors(errors),.valid_packets(packets));
    wire tx_byte_valid,tx_byte_error;wire [7:0] tx_byte;
    wire dummy_tx,dummy_busy;
    uart_phy #(.CLOCK_HZ(1152000),.BAUD(115200)) monitor(
        clk,rst_n,tx,dummy_tx,tx_byte_valid,tx_byte_error,tx_byte,1'b0,8'd0,dummy_busy);
    reg [7:0] reply[0:56];integer reply_count=0;
    always @(posedge clk) if(tx_byte_valid) begin
        if(reply_count>56) $fatal(1,"Too many reply bytes");
        reply[reply_count]=tx_byte;reply_count=reply_count+1;
    end
    function [15:0] crc_byte;
        input [15:0] old_crc;input [7:0] b;reg [15:0] c;integer k;
        begin c=old_crc^{b,8'd0};for(k=0;k<8;k=k+1)c=c[15]?(c<<1)^16'h1021:c<<1;crc_byte=c;end
    endfunction
    task send_byte;
        input [7:0] b;integer k;
        begin
            @(negedge clk);rx=0;repeat(10) @(negedge clk);
            for(k=0;k<8;k=k+1)begin rx=b[k];repeat(10) @(negedge clk);end
            rx=1;repeat(10) @(negedge clk);
        end
    endtask
    reg [511:0] payload,initial_cfg;
    reg [15:0] checksum;
    task send_packet;
        input [7:0] command,length;input [15:0] seq;input bad_crc;
        integer j;reg [7:0] b;
        begin
            checksum=16'hffff;
            send_byte(8'haa);send_byte(8'h55);
            send_byte(1);checksum=crc_byte(checksum,1);
            send_byte(command);checksum=crc_byte(checksum,command);
            send_byte(length);checksum=crc_byte(checksum,length);
            send_byte(seq[7:0]);checksum=crc_byte(checksum,seq[7:0]);
            send_byte(seq[15:8]);checksum=crc_byte(checksum,seq[15:8]);
            for(j=0;j<length;j=j+1) begin b=payload[j*8+:8];send_byte(b);checksum=crc_byte(checksum,b);end
            send_byte(checksum[7:0]^{7'd0,bad_crc});send_byte(checksum[15:8]);
            repeat(12) @(negedge clk);
        end
    endtask
    integer k;reg [15:0] response_crc;
    initial begin
        repeat(8) @(negedge clk);rst_n=1;
        repeat(8) @(negedge clk);initial_cfg=cfg;
        if(cfg[6*32+:32]!=98809312) $fatal(1,"Missing real boot calibration");
        payload=cfg;payload[0+:32]=178000;
        send_packet(8'h10,64,16'h1234,1);
        if(pending || cfg!==initial_cfg || errors!=1) $fatal(1,"Bad CRC changed configuration");
        send_packet(8'h10,64,16'h1235,0);
        if(!pending || cfg!==initial_cfg || active_seq!=0) $fatal(1,"Busy configuration changed");
        busy=0;repeat(4) @(negedge clk);
        if(pending || cfg!==payload || active_seq!=16'h1235) $fatal(1,"Atomic apply failed");
        busy=1;payload[6*32+:32]=0;
        send_packet(8'h10,64,16'h1236,0);
        if(pending || active_seq!=16'h1235 || errors!=2) $fatal(1,"Invalid focal length accepted");
        payload=cfg;payload[1*32+:32]=100;
        send_packet(8'h10,64,16'h1237,0);
        payload[1*32+:32]=200;
        send_packet(8'h10,64,16'h1238,0);
        if(active_seq!=16'h1235 || !pending) $fatal(1,"Pending overwrite violated frame atomicity");
        busy=0;repeat(4) @(negedge clk);
        if(cfg!==payload || active_seq!=16'h1238) $fatal(1,"Latest complete pending group not applied");
        payload[15*32+:32]=32'h0001beef;
        send_packet(8'h10,64,16'h1239,0);
        if(cfg!==payload || active_seq!=16'h1239) $fatal(1,"Feedback tag not accepted atomically");
        payload[15*32+18]=1;
        send_packet(8'h10,64,16'h123a,0);
        if(active_seq!=16'h1239 || errors!=3) $fatal(1,"Reserved marker flags accepted");
        initial_cfg=cfg;busy=1;payload=cfg;payload[14*32+:32]=32'h00080009;
        payload[15*32+:32]=32'hfffd1234;
        send_packet(8'h10,64,16'h123b,0);
        if(!pending || cfg!==initial_cfg)
            $fatal(1,"Projective parameters not accepted atomically pending=%b errors=%0d ok=%b reg14=%h reg15=%h",
                   pending,errors,dut.parameters_ok,payload[14*32+:32],payload[15*32+:32]);
        busy=0;repeat(4) @(negedge clk);
        if(cfg!==payload || active_seq!=16'h123b) $fatal(1,"Projective parameters not applied");
        busy=1;payload[14*32+4]=1;
        send_packet(8'h10,64,16'h123c,0);
        if(active_seq!=16'h123b || errors!=4) $fatal(1,"Reserved projective flag accepted");
        send_packet(8'h20,0,16'habcd,0);
        wait(reply_count==57);repeat(20) @(negedge clk);
        if(reply[0]!=8'haa || reply[1]!=8'h55 || reply[3]!=8'ha0 || reply[4]!=48 ||
           reply[5]!=8'hcd || reply[6]!=8'hab) $fatal(1,"Response header");
        response_crc=16'hffff;
        for(k=2;k<=54;k=k+1)response_crc=crc_byte(response_crc,reply[k]);
        if({reply[56],reply[55]}!==response_crc) $fatal(1,"Response CRC");
        if({reply[12],reply[11]}!=16'h123b) $fatal(1,"Response active active_seq");
        reply_count=0;
        send_packet(8'h21,0,16'habce,0);
        wait(reply_count==57);repeat(20) @(negedge clk);
        if(reply[3]!=8'ha1 || {reply[10],reply[9],reply[8],reply[7]}!=32'h534d5432)
            $fatal(1,"Smooth telemetry identity");
        if({reply[14],reply[13],reply[12],reply[11]}!=3 ||
           {reply[18],reply[17],reply[16],reply[15]}!=32'h89abcdef ||
           {reply[54],reply[53],reply[52],reply[51]}!=32'h00020001)
            $fatal(1,"Smooth telemetry fields");
        response_crc=16'hffff;
        for(k=2;k<=54;k=k+1)response_crc=crc_byte(response_crc,reply[k]);
        if({reply[56],reply[55]}!==response_crc) $fatal(1,"Smooth telemetry CRC");
        reply_count=0;
        send_packet(8'h22,0,16'habcf,0);
        wait(reply_count==57);repeat(20) @(negedge clk);
        if(reply[3]!=8'ha2 || {reply[10],reply[9],reply[8],reply[7]}!=32'h494d5501)
            $fatal(1,"IMU snapshot protocol");
        response_crc=16'hffff;
        for(k=2;k<=54;k=k+1)response_crc=crc_byte(response_crc,reply[k]);
        if({reply[56],reply[55]}!==response_crc) $fatal(1,"IMU CRC");
        payload=1;send_packet(8'h23,1,16'habd0,0);
        if(dut.imu_baud_code!=1) $fatal(1,"Receiver baud setting");
        payload=5;send_packet(8'h23,1,16'habd1,0);
        if(dut.imu_baud_code!=1) $fatal(1,"Invalid receiver baud accepted");
        send_packet(8'h24,0,16'habd2,0);
        if(dut.imu_restart!=1) $fatal(1,"BNO reset toggle");
        payload=1;send_packet(8'h26,1,16'habd4,0);
        if(!map_enable || !dut.imu_capture_toggle || map_update_count!=1 || !map_update_state)
            $fatal(1,"Pose-map capture/enable command did not publish synchronized state");
        payload=0;send_packet(8'h26,1,16'habd5,0);
        if(map_enable || !dut.imu_capture_toggle || map_update_count!=2 || map_update_state)
            $fatal(1,"Pose-map disable command did not publish synchronized state");
        payload=2;send_packet(8'h26,1,16'habd6,0);
        if(dut.imu_map_enable || errors!=6) $fatal(1,"Invalid pose-map command accepted enabled=%b errors=%0d",dut.imu_map_enable,errors);
        reply_count=0;payload=3;k=errors;send_packet(8'h30,1,16'habd7,1);
        if(dut.sharpen_level!=0 || errors!=k+1 || reply_count!=0)
            $fatal(1,"Bad-CRC quality command changed state or returned success");
        reply_count=0;send_packet(8'h20,0,16'habd8,0);k=packets;
        payload=3;send_packet(8'h32,1,16'habd9,0);
        if(dut.denoise_level!=0 || packets!=k)
            $fatal(1,"Quality command was accepted while the UART response was busy");
        wait(reply_count==57);repeat(20) @(negedge clk);
        if(reply_count!=57 || reply[3]!=8'ha0)
            $fatal(1,"Busy-time quality command corrupted the in-flight STATUS response");
        reply_count=0;payload=2;send_packet(8'h30,1,16'habd7,0);
        wait(reply_count==57);repeat(20) @(negedge clk);
        if(dut.sharpen_level!=2 || reply[3]!=8'hb0 || {reply[6],reply[5]}!=16'habd7 ||
           {reply[10],reply[9],reply[8],reply[7]}!=32'h4b434151 ||
           reply[11]!=1 || reply[12]!=8'h30 || reply[13]!=2 || reply[14]!=0)
            $fatal(1,"Sharpen QACK did not match accepted request");
        response_crc=16'hffff;
        for(k=2;k<=54;k=k+1)response_crc=crc_byte(response_crc,reply[k]);
        if({reply[56],reply[55]}!==response_crc) $fatal(1,"Sharpen QACK CRC");
        reply_count=0;payload=3;send_packet(8'h32,1,16'habd8,0);
        wait(reply_count==57);repeat(20) @(negedge clk);
        if(dut.denoise_level!=3 || reply[3]!=8'hb2 || {reply[6],reply[5]}!=16'habd8 ||
           {reply[10],reply[9],reply[8],reply[7]}!=32'h4b434151 ||
           reply[11]!=1 || reply[12]!=8'h32 || reply[13]!=3 || reply[14]!=0)
            $fatal(1,"Denoise QACK did not match accepted request");
        response_crc=16'hffff;
        for(k=2;k<=54;k=k+1)response_crc=crc_byte(response_crc,reply[k]);
        if({reply[56],reply[55]}!==response_crc) $fatal(1,"Denoise QACK CRC");
        reply_count=0;payload=4;send_packet(8'h30,1,16'habd9,0);
        if(dut.sharpen_level!=2 || errors!=8 || reply_count!=0)
            $fatal(1,"Invalid quality level changed state or returned success");
        payload=0;payload[7:0]=3;payload[8+:8]=8'h41;payload[16+:8]=8'h42;
        send_packet(8'h34,49,16'habda,0);
        if(!osd_seen || osd_row_seen!=3 || osd_data_seen[7:0]!=8'h41 || osd_data_seen[15:8]!=8'h42)
            $fatal(1,"OSD row payload/sequence was not transferred");
        payload=4;send_packet(8'h34,49,16'habdb,0);
        if(errors!=9) $fatal(1,"Out-of-range OSD row was accepted");
        payload=1;send_packet(8'h35,1,16'habdc,0);
        if(!dut.osd_visible) $fatal(1,"OSD visibility command was not accepted");
        reply_count=0;send_packet(8'h25,0,16'habd3,0);
        wait(reply_count==57);repeat(20) @(negedge clk);
        if(reply[3]!=8'ha5 || {reply[10],reply[9],reply[8],reply[7]}!=32'h424e4401)
            $fatal(1,"BNO diagnostics response");
        response_crc=16'hffff;
        for(k=2;k<=54;k=k+1)response_crc=crc_byte(response_crc,reply[k]);
        if({reply[56],reply[55]}!==response_crc) $fatal(1,"BNO diagnostic CRC");
        $display("PASS host_control CRC, bounds, frame atomicity, pending replacement, status and IMU commands");$finish;
    end
    initial begin #20000000;$fatal(1,"Timeout");end
endmodule
