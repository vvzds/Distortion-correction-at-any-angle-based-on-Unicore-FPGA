`timescale 1ns/1ps
// Autonomous BNO085 SPI/SHTP endpoint. 0=Game RV+gyro, 1=ARVR Game RV+gyro,
// 2=Gyro Integrated RV (experimental). 200Hz requests, no flash/FRS writes.
// Snapshot publication is atomic per complete report. Unsupported/truncated
// cargo is discarded, never interpreted as a partial quaternion.
module bno085_bridge #(parameter CLOCK_HZ=125000000, SPI_HALF_DIV=64)(
    input wire clk,rst_n,miso,int_n,
    output wire sck,mosi,
    output reg cs_n,sensor_rst_n,wake_n,
    input wire [2:0] mode,
    input wire restart,frame_update,
    output wire [383:0] snapshot,diagnostics
);
    localparam US_DIV=CLOCK_HZ/1000000;
    localparam PERIOD_US=5000;
    reg [15:0] us_div;
    reg [31:0] now_us,frame_us,frames,irq_us,transaction_us;
    (* syn_preserve=1 *) reg [1:0] int_sync;
    reg int_previous;
    reg [31:0] pose_us,gyro_us,errors,seq_gaps,oversize,resets,transactions;
    reg [23:0] pose_count;
    reg [63:0] quaternion,gyro;
    reg [1:0] seen;
    reg [31:0] pose_interval,gyro_interval,part_number,build_number;
    reg [15:0] version;
    reg [7:0] status_bits;
    wire [7:0] pose_id=mode==1?8'h29:mode==2?8'h2a:8'h08;
    assign snapshot={mode,3'd0,seen,pose_count,errors,quaternion,pose_us,
                     resets[15:0],gyro[47:0],gyro_us,frames,frame_us,now_us,32'h424e4f01};
    assign diagnostics={build_number,part_number,gyro_interval,pose_interval,
                        transactions,oversize,seq_gaps,resets,
                        version,status_bits,pose_id,32'd5000,now_us,32'h424e4401};
    reg [2:0] old_mode;
    reg old_restart;
    reg [31:0] deadline,watchdog,last_data_us;
    // Break now_us subtraction -> compare -> FSM/output enable into stages.
    // This is slow control with >=1us waits; one 8ns stage is immaterial.
    reg [31:0] deadline_age,watchdog_age,data_age;
    reg [4:0] state;
    reg [3:0] init_step,tx_kind;
    reg [7:0] tx_seq,rx_channel,rx_sequence;
    reg [7:0] expected_seq[0:5];
    reg [5:0] seq_seen;
    reg [15:0] index,rx_length,transfer_length,tx_length,payload_length,cursor;
    reg [7:0] length_low;
    reg continuation,discard,transmit;
    reg [7:0] payload[0:511];
    reg [31:0] reference_delta;
    reg [135:0] report_buffer;
    reg [4:0] fetch_index;
    wire [7:0] report_id=report_buffer[7:0];
    wire [31:0] report_timebase=report_buffer[8+:32];
    wire [15:0] report_delay={2'b0,report_buffer[18+:6],report_buffer[24+:8]};
    wire [31:0] sample_us=transaction_us+(reference_delta+report_delay)*32'd100;
    wire [63:0] report_quat=report_buffer[32+:64];
    reg [7:0] report_length;
    always @* begin
        case(report_id)
            8'hfb,8'hfa:report_length=5;
            8'h02,8'h01,8'h04,8'h06:report_length=10;
            8'h08,8'h29:report_length=12;
            8'h05,8'h09,8'h28:report_length=14;
            8'hf8,8'hf1:report_length=16;
            8'hfc:report_length=17;
            8'hef:report_length=2;
            default:report_length=0;
        endcase
    end
    reg byte_start;
    reg [7:0] tx_byte;
    wire byte_busy,byte_done;wire [7:0] rx_byte;
    bno_spi_byte #(.HALF_DIV(SPI_HALF_DIV)) phy(clk,rst_n,byte_start,tx_byte,miso,
                                                sck,mosi,byte_busy,byte_done,rx_byte);
    // Outgoing channel 2 sequence is independent from incoming channel seqs.
    always @* begin
        tx_byte=0;
        if(transmit && index<tx_length) begin
            case(index)
                0:tx_byte=tx_length[7:0];1:tx_byte=0;2:tx_byte=2;3:tx_byte=tx_seq;
                4:tx_byte=tx_kind==0?8'hf9:tx_kind>=3?8'hfe:8'hfd;
                5:tx_byte=tx_kind==0?0:(tx_kind==2 || tx_kind==4)?8'h02:pose_id;
                9:tx_byte=8'h88;10:tx_byte=8'h13; // 5000us LE, only SET has these bytes
                default:tx_byte=0;
            endcase
        end
    end
    integer k;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            us_div<=0;now_us<=0;frame_us<=0;frames<=0;irq_us<=0;transaction_us<=0;
            int_sync<=3;int_previous<=1;cs_n<=1;sensor_rst_n<=0;wake_n<=1;
            pose_us<=0;gyro_us<=0;errors<=0;seq_gaps<=0;oversize<=0;resets<=0;
            transactions<=0;pose_count<=0;quaternion<=0;gyro<=0;seen<=0;
            pose_interval<=0;gyro_interval<=0;part_number<=0;build_number<=0;version<=0;status_bits<=0;
            old_mode<=0;old_restart<=0;deadline_age<=0;watchdog_age<=0;data_age<=0;deadline<=0;watchdog<=0;last_data_us<=0;state<=0;
            init_step<=0;tx_kind<=0;tx_seq<=0;rx_channel<=0;rx_sequence<=0;seq_seen<=0;
            index<=0;rx_length<=0;transfer_length<=0;tx_length<=0;payload_length<=0;cursor<=0;
            length_low<=0;continuation<=0;discard<=0;transmit<=0;reference_delta<=0;byte_start<=0;report_buffer<=0;fetch_index<=0;
            for(k=0;k<6;k=k+1) expected_seq[k]<=0;
        end else begin
            deadline_age<=now_us-deadline;watchdog_age<=now_us-watchdog;data_age<=now_us-last_data_us;
            byte_start<=0;int_sync<={int_sync[0],int_n};int_previous<=int_sync[1];
            if(int_previous && !int_sync[1]) irq_us<=now_us;
            if(us_div==US_DIV-1) begin us_div<=0;now_us<=now_us+1'b1;end
            else us_div<=us_div+1'b1;
            if(frame_update) begin frame_us<=now_us;frames<=frames+1'b1;end
            old_mode<=mode;old_restart<=restart;
            // Changing report mode resets/reconfigures all volatile features.
            if(mode!=old_mode || restart!=old_restart) begin
                state<=0;deadline<=now_us;deadline_age<=0;seen<=0;cs_n<=1;sensor_rst_n<=0;wake_n<=1;
            end else case(state)
                0:begin
                    cs_n<=1;wake_n<=1;sensor_rst_n<=0;seen<=0;seq_seen<=0;
                    tx_seq<=0;init_step<=0;pose_interval<=0;gyro_interval<=0;status_bits<=0;
                    if(deadline_age>=1000 && !byte_busy) begin
                        sensor_rst_n<=1;deadline<=now_us;deadline_age<=0;resets<=resets+1'b1;state<=1;
                    end
                end
                1:if(!int_sync[1] && deadline_age>=1000) begin
                    deadline<=now_us;deadline_age<=0;state<=2;last_data_us<=now_us;data_age<=0;
                end else if(deadline_age>200000) begin
                    status_bits[7]<=1;state<=2;init_step<=5;errors<=errors+1'b1;
                end
                2:begin
                    cs_n<=1;wake_n<=1;
                    // Drain interrupts promptly. Configure only between incoming cargos.
                    if(!int_sync[1]) begin
                        transmit<=0;tx_length<=0;transfer_length<=4;index<=0;
                        transaction_us<=int_previous?now_us:irq_us;
                        discard<=0;rx_length<=0;state<=4;cs_n<=0;watchdog<=now_us;watchdog_age<=0;
                    end else if(init_step<5 && deadline_age>=1000) begin
                        // GIRV supplies gyro together with quaternion; skip standalone gyro.
                        if(mode==2 && (init_step==2 || init_step==4)) init_step<=init_step+1'b1;
                        else begin
                            tx_kind<=init_step;tx_length<=(init_step==0 || init_step>=3)?6:21;
                            transmit<=1;wake_n<=0;watchdog<=now_us;watchdog_age<=0;state<=3;
                        end
                    end else if(seen!=0 && data_age>500000) begin
                        // Fault holds data invalid; no autonomous reboot loop.
                        seen<=0;status_bits[7]<=1;
                    end
                end
                3:if(!int_sync[1]) begin
                    cs_n<=0;transfer_length<=tx_length;index<=0;discard<=0;rx_length<=0;
                    transaction_us<=int_previous?now_us:irq_us;watchdog<=now_us;watchdog_age<=0;state<=4;
                end else if(watchdog_age>10000) begin
                    errors<=errors+1'b1;wake_n<=1;seen<=0;status_bits[7]<=1;
                    init_step<=5;state<=2;
                end
                4:if(!byte_busy) begin byte_start<=1;state<=5;end
                5:if(byte_done) begin
                    if(index==0) length_low<=rx_byte;
                    if(index==1) begin
                        rx_length<={1'b0,rx_byte[6:0],length_low};continuation<=rx_byte[7];
                        if({rx_byte[6:0],length_low}>4096) begin discard<=1;errors<=errors+1'b1;end
                    end
                    if(index==2) rx_channel<=rx_byte;
                    if(index==3) begin
                        rx_sequence<=rx_byte;
                        if(rx_length>transfer_length && rx_length<=4096) transfer_length<=rx_length;
                        if(rx_length>516) begin discard<=1;oversize<=oversize+1'b1;end
                    end
                    if(index>=4 && index<rx_length && index<516) payload[index-4]<=rx_byte;
                    // At byte 3, use freshly parsed RX length to avoid ending at
                    // header when the slave has a larger full-duplex cargo.
                    if(index+1>=transfer_length && !(index==3 && rx_length>transfer_length && rx_length<=4096)) begin
                        deadline<=now_us;deadline_age<=0;state<=6;
                    end else begin index<=index+1'b1;state<=4;end
                end
                6:if(deadline_age>=2) begin
                    cs_n<=1;wake_n<=1;transactions<=transactions+1'b1;
                    if(transmit) begin tx_seq<=tx_seq+1'b1;init_step<=init_step+1'b1;end
                    payload_length<=rx_length>=4?rx_length-4:0;
                    cursor<=0;reference_delta<=0;
                    if(rx_length==0) state<=2;
                    else if(discard || continuation || rx_length<4 || rx_channel>5) begin
                        errors<=errors+1'b1;state<=2;
                    end else begin
                        if(seq_seen[rx_channel] && expected_seq[rx_channel]!=rx_sequence) seq_gaps<=seq_gaps+1'b1;
                        seq_seen[rx_channel]<=1;expected_seq[rx_channel]<=rx_sequence+1'b1;
                        state<=7;
                    end
                end
                7:begin
                    if(cursor>=payload_length || rx_channel==0) state<=2;
                    else begin fetch_index<=0;report_buffer<=0;state<=8;end
                end
                8:begin
                    if(cursor+fetch_index<payload_length)
                        report_buffer[fetch_index*8+:8]<=payload[(cursor+fetch_index)&511];
                    if(fetch_index==16) state<=9;
                    else fetch_index<=fetch_index+1'b1;
                end
                9:begin
                    if(rx_channel==1) begin
                        if(report_id==1) begin
                            seen<=0;resets<=resets+1'b1;init_step<=0;tx_seq<=0;
                            pose_interval<=0;gyro_interval<=0;deadline<=now_us;deadline_age<=0;
                        end
                        state<=2;
                    end else if(rx_channel==5) begin
                        if(mode==2 && cursor+14<=payload_length) begin
                            quaternion<=report_buffer[0+:64];gyro<={16'd0,report_buffer[64+:48]};
                            gyro_us<=transaction_us;pose_us<=transaction_us;seen<=3;
                            pose_count<=pose_count+1'b1;last_data_us<=now_us;data_age<=0;cursor<=cursor+14;state<=7;
                        end else begin errors<=errors+1'b1;state<=2;end
                    end else if(report_length==0 || cursor+report_length>payload_length) begin
                        errors<=errors+1'b1;state<=2;
                    end else begin
                        cursor<=cursor+report_length;state<=7;
                        if(rx_channel==2 && report_id==8'hf8) begin
                            version<={report_buffer[16+:8],report_buffer[24+:8]};
                            part_number<=report_buffer[32+:32];build_number<=report_buffer[64+:32];status_bits[0]<=1;
                        end
                        if(rx_channel==2 && report_id==8'hfc) begin
                            if(report_buffer[8+:8]==pose_id) begin
                                pose_interval<=report_buffer[40+:32];status_bits[1]<=1;
                            end
                            if(report_buffer[8+:8]==2) begin
                                gyro_interval<=report_buffer[40+:32];status_bits[2]<=1;
                            end
                        end
                        if(rx_channel==3 || rx_channel==4) begin
                            if(report_id==8'hfb) reference_delta<=-report_timebase;
                            if(report_id==8'hfa) reference_delta<=reference_delta+report_timebase;
                            if(report_id==pose_id && mode!=2) begin
                                quaternion<=report_quat;pose_us<=sample_us;seen[1]<=1;
                                pose_count<=pose_count+1'b1;last_data_us<=now_us;data_age<=0;
                            end
                            if(report_id==2 && mode!=2) begin
                                gyro<={16'd0,report_buffer[32+:48]};gyro_us<=sample_us;seen[0]<=1;
                            end
                        end
                    end
                end
                default:state<=0;
            endcase
            if((state==4 || state==5) && watchdog_age>50000) begin
                cs_n<=1;wake_n<=1;errors<=errors+1'b1;seen<=0;state<=2;init_step<=5;
            end
        end
    end
endmodule
