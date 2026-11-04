`timescale 1ns/1ps
// Receive-only WitMotion 11-byte snapshots. No unsolicited host UART traffic,
// no sensor configuration writes. All times are packet HEADER receipt in us.
module imu_bridge #(parameter CLOCK_HZ=125000000)(
    input wire clk,rst_n,rx,
    input wire [2:0] baud_code,
    input wire frame_update,
    output wire [383:0] snapshot
);
    localparam US_DIV=CLOCK_HZ/1000000;
    reg [15:0] us_divider;
    reg [31:0] now_us,frame_us,frames;
    reg [31:0] gyro_us,angle_us,errors;
    reg [23:0] packets;
    reg [63:0] gyro,angle;
    reg [1:0] seen;
    assign snapshot={baud_code,3'd0,seen,packets,errors,angle,angle_us,
                     gyro,gyro_us,frames,frame_us,now_us,32'h494d5501};
    // Independent variable-baud receiver, two-stage synchronizer. A baud
    // change discards partial packets; code changes never configure the IMU.
    (* syn_preserve=1 *) reg [1:0] rx_sync;
    reg [15:0] divider,rc;
    reg [2:0] last_baud,rb;
    reg [1:0] rs;
    reg [7:0] shift,byte_data;
    reg byte_valid,byte_error;
    always @* case(baud_code)
        1:divider=CLOCK_HZ/115200;
        2:divider=CLOCK_HZ/57600;
        3:divider=CLOCK_HZ/38400;
        4:divider=CLOCK_HZ/19200;
        default:divider=CLOCK_HZ/9600;
    endcase
    reg [3:0] index;
    reg [7:0] kind,sum;
    reg [63:0] data;
    reg [31:0] header_us;
    reg [21:0] timeout_count;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            rx_sync<=3;last_baud<=0;rs<=0;rc<=0;rb<=0;shift<=0;
            byte_data<=0;byte_valid<=0;byte_error<=0;
        end else begin
            rx_sync<={rx_sync[0],rx};last_baud<=baud_code;
            byte_valid<=0;byte_error<=0;
            if(last_baud!=baud_code) rs<=0;
            else case(rs)
                0:if(!rx_sync[1]) begin rc<=divider/2-1;rs<=1;end
                1:if(rc!=0) rc<=rc-1'b1;
                  else if(!rx_sync[1]) begin rc<=divider-1;rb<=0;rs<=2;end
                  else rs<=0;
                2:if(rc!=0) rc<=rc-1'b1;
                  else begin
                      shift[rb]<=rx_sync[1];rc<=divider-1;
                      if(rb==7) rs<=3;else rb<=rb+1'b1;
                  end
                3:if(rc!=0) rc<=rc-1'b1;
                  else begin rs<=0;
                      if(rx_sync[1]) begin byte_valid<=1;byte_data<=shift;end
                      else byte_error<=1;
                  end
            endcase
        end
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            us_divider<=0;now_us<=0;frame_us<=0;frames<=0;
            gyro_us<=0;angle_us<=0;errors<=0;packets<=0;gyro<=0;angle<=0;seen<=0;
            index<=0;kind<=0;sum<=0;data<=0;header_us<=0;timeout_count<=0;
        end else begin
            if(us_divider==US_DIV-1) begin us_divider<=0;now_us<=now_us+1'b1;end
            else us_divider<=us_divider+1'b1;
            if(frame_update) begin frame_us<=now_us;frames<=frames+1'b1;end
            if(index!=0) timeout_count<=timeout_count+1'b1;else timeout_count<=0;
            if(last_baud!=baud_code) begin index<=0;seen<=0;end
            else if(byte_error || (index!=0 && timeout_count>=CLOCK_HZ/50)) begin
                index<=0;timeout_count<=0;errors<=errors+1'b1;
            end else if(byte_valid) begin
                timeout_count<=0;
                if(index==0) begin
                    if(byte_data==8'h55) begin index<=1;sum<=8'h55;header_us<=now_us;end
                end else if(index==1) begin
                    if(byte_data>=8'h50 && byte_data<=8'h59) begin
                        kind<=byte_data;sum<=sum+byte_data;index<=2;
                    end else if(byte_data==8'h55) begin sum<=8'h55;header_us<=now_us;end
                    else begin index<=0;errors<=errors+1'b1;end
                end else if(index<10) begin
                    data[(index-2)*8+:8]<=byte_data;sum<=sum+byte_data;index<=index+1'b1;
                end else begin
                    index<=0;
                    if(byte_data==sum) begin
                        if(kind==8'h52) begin gyro<=data;gyro_us<=header_us;seen[0]<=1;end
                        if(kind==8'h53) begin
                            angle<=data;angle_us<=header_us;seen[1]<=1;packets<=packets+1'b1;
                        end
                    end else begin
                        errors<=errors+1'b1;
                        if(byte_data==8'h55) begin index<=1;sum<=8'h55;header_us<=now_us;end
                    end
                end
            end
        end
    end
endmodule
