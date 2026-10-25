`timescale 1ns/1ps
// 独立候选：总线事务层由外部SCCB主机提供，同一时钟域，禁止并发初始化。
// cmd=0锁定并快照，cmd=1恢复原自动模式，cmd=2复核快照。
module ov5640_quality_lock #(
    parameter TIMEOUT_CYCLES = 25000000
)(
    input wire clk, input wire rst_n,
    input wire init_done, input wire start, input wire [1:0] cmd,
    output wire busy, output reg done, output reg error,output reg abort_bus,
    output reg locked, output reg recovery_required,
    output reg snapshot_valid, output reg [119:0] snapshot,
    output wire req_valid, input wire req_ready,
    output wire req_read, output wire [15:0] req_addr,
    output wire [7:0] req_wdata,
    input wire rsp_valid, input wire rsp_error, input wire [7:0] rsp_rdata
);
    localparam IDLE=0,ISSUE=1,WAIT_RSP=2,NEXT=3;
    reg [1:0] state;
    reg [2:0] phase;
    reg [4:0] index;
    reg [31:0] timer;
    reg original_valid;
    reg [7:0] ae_original,wb_original;
    reg [7:0] expected [0:14];
    reg [1:0] operation;
    reg [15:0] addr;
    reg [7:0] wdata;
    reg read_op;
    integer k;
    // 快照顺序：模式2字节、曝光3、增益2、额外VTS2、AWB RGB各2。
    function [15:0] address;
        input [4:0] n;
        begin
            case(n)
              0:address=16'h3503; 1:address=16'h3406;
              2:address=16'h3500; 3:address=16'h3501; 4:address=16'h3502;
              5:address=16'h350a; 6:address=16'h350b;
              7:address=16'h350c; 8:address=16'h350d;
              9:address=16'h3400;10:address=16'h3401;11:address=16'h3402;
             12:address=16'h3403;13:address=16'h3404;14:address=16'h3405;
             default:address=16'hffff;
            endcase
        end
    endfunction
    assign busy=(state!=IDLE);
    assign req_valid=(state==ISSUE);
    assign req_read=read_op;
    assign req_addr=addr;
    assign req_wdata=wdata;
    always @* begin
        read_op=1'b1;addr=address(index);wdata=0;
        if(operation==0) begin
            case(phase)
             0:begin addr=address(index);end
             1:begin read_op=0;addr=16'h3503;wdata=ae_original|8'h03;end
             2:begin addr=address(index);end
             3:begin read_op=0;addr=16'h3406;wdata=wb_original|8'h01;end
             4:begin read_op=0;addr=address(index);wdata=expected[index];end
             default:begin addr=address(index);end
            endcase
        end else if(operation==1) begin
            addr=address(index);
            if(phase==0) begin read_op=0;wdata=(index==0)?ae_original:wb_original;end
        end
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=IDLE;phase<=0;index<=0;operation<=0;timer<=0;
            done<=0;error<=0;abort_bus<=0;locked<=0;recovery_required<=0;
            original_valid<=0;ae_original<=0;wb_original<=0;
            snapshot_valid<=0;snapshot<=0;
            for(k=0;k<15;k=k+1) expected[k]<=0;
        end else begin
            done<=0;abort_bus<=0;
            if(state!=IDLE && timer==TIMEOUT_CYCLES-1) begin
                state<=IDLE;done<=1;error<=1;locked<=0;snapshot_valid<=0;
                recovery_required<=original_valid;abort_bus<=1;
            end else begin
                if(state!=IDLE) timer<=timer+1'b1;
                case(state)
                 IDLE:if(start) begin
                    error<=0;timer<=0;operation<=cmd;phase<=0;index<=0;
                    if(!init_done || cmd==3 ||
                       (cmd==0 && (locked || recovery_required)) ||
                       (cmd==1 && !original_valid) || (cmd==2 && !locked)) begin
                        done<=1;error<=1;
                    end else begin
                        state<=ISSUE;
                        if(cmd==0) begin snapshot_valid<=0;original_valid<=0;end
                        if(cmd==2) phase<=5;
                    end
                 end
                 ISSUE:if(req_ready) state<=WAIT_RSP;
                 WAIT_RSP:if(rsp_valid) begin
                    if(rsp_error) begin
                        state<=IDLE;done<=1;error<=1;locked<=0;snapshot_valid<=0;
                        recovery_required<=original_valid;
                    end else if(read_op) begin
                        if(operation==0 && phase==0) begin
                            if(index==0) begin ae_original<=rsp_rdata;expected[0]<=rsp_rdata|8'h03;end
                            else begin wb_original<=rsp_rdata;expected[1]<=rsp_rdata|8'h01;original_valid<=1;end
                            state<=NEXT;
                        end else if(operation==0 && phase==2) begin
                            expected[index]<=rsp_rdata;state<=NEXT;
                        end else if(operation==1) begin
                            if(rsp_rdata!=((index==0)?ae_original:wb_original)) begin
                                state<=IDLE;done<=1;error<=1;locked<=0;
                                snapshot_valid<=0;recovery_required<=1;
                            end else state<=NEXT;
                        end else if(rsp_rdata!=expected[index]) begin
                            state<=IDLE;done<=1;error<=1;locked<=0;
                            snapshot_valid<=0;recovery_required<=1;
                        end else begin snapshot[index*8+:8]<=rsp_rdata;state<=NEXT;end
                    end else state<=NEXT;
                 end
                 NEXT:begin
                    state<=ISSUE;
                    if(operation==1) begin
                        if(index==1) begin
                            if(phase==0) begin phase<=1;index<=0;end
                            else begin
                                state<=IDLE;done<=1;locked<=0;recovery_required<=0;
                                original_valid<=0;snapshot_valid<=0;
                            end
                        end else index<=index+1'b1;
                    end else if(operation==2 || phase==5) begin
                        if(index==14) begin
                            state<=IDLE;done<=1;locked<=1;snapshot_valid<=1;recovery_required<=0;
                        end else index<=index+1'b1;
                    end else case(phase)
                      0:if(index==1) begin phase<=1;index<=0;end else index<=1;
                      1:begin phase<=3;index<=0;end
                      2:if(index==14) begin phase<=4;index<=9;end else index<=index+1'b1;
                      3:begin phase<=2;index<=2;end
                      4:if(index==14) begin phase<=5;index<=0;end else index<=index+1'b1;
                      default:begin state<=IDLE;done<=1;error<=1;end
                    endcase
                 end
                 default:state<=IDLE;
                endcase
            end
        end
    end
endmodule
