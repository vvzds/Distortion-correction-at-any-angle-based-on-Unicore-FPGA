`timescale 1ns/1ps
module p8_touch_exhaustive_tb;
reg clk=0;always #4 clk=~clk;
reg rst_n=0,clear=0,touch=0;
reg [31:0] ids=0;
reg [21:0] seq=0;
undistort_cache_ab dut(.clk(clk),.rst_n(rst_n),.i_frame_clear(clear),.i_line_mode(1'b0),
 .i_load_begin(1'b0),.i_load_bank(8'd0),.i_load_row(11'd0),.i_load_vld(1'b0),.i_load_last(1'b0),.i_load_data(256'd0),
 .i_query_row_a(11'd0),.i_query_row_b(11'd0),.i_prefetch_row(11'd0),
 .i_sample_req(1'b0),.i_sample_bank_a(8'd0),.i_sample_bank_b(8'd0),.i_sample_bank_a1(8'd0),.i_sample_bank_b1(8'd0),.i_sample_x(11'd0),
 .i_lookup_req(1'b0),.i_lookup_a(11'd0),.i_lookup_b(11'd0),.i_lookup_x(11'd0),.i_lookup_seq(22'd0),
 .i_touch(touch),.i_touch_ids(ids),.i_touch_seq(seq),.i_retired_count(22'd0),.i_ready_ids(32'd0),.i_fetch_gnt(1'b0));
reg [191:0] expected;
reg [21:0] ages[0:191];
integer lane,id,en,s,checks=0,seed=32'h375ba927;
task check_update;
begin
 #1;expected=0;
 for(s=0;s<4;s=s+1)if(touch && ids[s*8+:8]<192)expected[ids[s*8+:8]]=1'b1;
 if(dut.age_touch_mask!==expected)$fatal(1,"touch mask mismatch ids=%h touch=%b",ids,touch);
 @(posedge clk);
 if(rst_n && !clear)for(s=0;s<192;s=s+1)if(expected[s])ages[s]=seq;
 #1;for(s=0;s<192;s=s+1)if(dut.last_use[s]!==ages[s])$fatal(1,"touch timestamp mismatch slot=%0d ids=%h",s,ids);
 checks=checks+1;
end endtask
initial begin
 for(s=0;s<192;s=s+1)begin dut.last_use[s]=0;ages[s]=0;end
 repeat(2)@(negedge clk);rst_n=1;
 // Include invalid 192..255 IDs; each lane must independently decode all slots.
 for(lane=0;lane<4;lane=lane+1)for(id=0;id<256;id=id+1)for(en=0;en<2;en=en+1)begin
  @(negedge clk);ids=32'hffffffff;ids[lane*8+:8]=id;touch=en;seq=seq+1;check_update;
 end
 // Duplicate IDs, independently mixed banks, and reset/frame-clear suppression.
 for(id=0;id<192;id=id+1)begin
  @(negedge clk);ids={4{id[7:0]}};touch=1;seq=seq+1;check_update;
 end
 for(id=0;id<512;id=id+1)begin
  @(negedge clk);ids=$random(seed);touch=id%3!=0;clear=id%13==0;rst_n=id%17!=0;seq=seq+1;check_update;
 end
 $display("P8_TOUCH_EXHAUSTIVE PASS checks=%0d lanes=4 ids_per_lane=256 enable_values=2 duplicates=192 mixed=512",checks);$finish;
end
initial begin #100000;$fatal(1,"watchdog");end
endmodule
