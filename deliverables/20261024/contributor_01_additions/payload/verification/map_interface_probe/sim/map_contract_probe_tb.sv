`timescale 1ns/1ps
// Interface characterization only. This is not the full Brown4 numerical suite.
module map_contract_probe_tb;
  reg clk=0; always #4 clk=~clk;
  reg rst_n=0, i_frame_init=0, i_valid=0, i_aff_en=0;
  reg signed [31:0] i_fx=32'sh03e80000, i_fy=32'sh03e80000;
  reg signed [31:0] i_cx=32'sh03c00000, i_cy=32'sh021c0000;
  reg signed [31:0] i_k1=0,i_k2=0,i_p1=0,i_p2=0;
  reg signed [31:0] i_aff_a11=65536,i_aff_a12=0,i_aff_a21=0,i_aff_a22=65536;
  reg signed [31:0] i_aff_tx=0,i_aff_ty=0;
  reg [10:0] i_u=0,i_v=0;
  wire o_init_done,o_valid;
  wire [26:0] o_sx_q16,o_sy_q16;
  undistort_map dut(.*);
  integer cycle=0, head=0,tail=0, accepted=0,returned=0,discarded=0;
  integer expected_latency=11, init_limit=128, init_edge=-1, init_count=0;
  integer last_return=-1, adjacent_returns=0, measured_latency=-1;
  integer q_cycle[0:4095];
  reg [26:0] q_x[0:4095],q_y[0:4095];
  reg pre_init, pre_accept, pre_ready;

  always @(posedge clk) begin
    cycle=cycle+1;
    pre_init=i_frame_init; pre_ready=o_init_done;
    pre_accept=i_valid && o_init_done;
    if(!rst_n) begin
      discarded=discarded+(tail-head); head=0;tail=0;init_edge=-1;
      #1;
      if(o_valid!==0 || o_init_done!==0) $fatal(1,"RESET_NOT_CLEARED");
    end else begin
      if(pre_init) init_edge=cycle;
      if(pre_accept) begin
        if(tail>=4096) $fatal(1,"TB_QUEUE_FULL");
        q_cycle[tail]=cycle; q_x[tail]={i_u,16'd0}; q_y[tail]={i_v,16'd0};
        tail=tail+1;accepted=accepted+1;
      end
      #1;
      if(pre_init && o_init_done!==0) $fatal(1,"INIT_NOT_BUSY");
      if(init_edge>=0 && !pre_ready && o_init_done===1) begin
        $display("INIT index=%0d edge_distance=%0d",init_count,cycle-init_edge);
        if(cycle-init_edge>init_limit) $fatal(1,"INIT_TIMEOUT_BOUND");
        init_count=init_count+1;init_edge=-1;
      end
      if(o_valid===1) begin
        if(head>=tail) $fatal(1,"UNEXPECTED_OUTPUT cycle=%0d",cycle);
        if(cycle-q_cycle[head]!=expected_latency)
          $fatal(1,"VALID_LATENCY expected=%0d actual=%0d",expected_latency,cycle-q_cycle[head]);
        if(o_sx_q16!==q_x[head] || o_sy_q16!==q_y[head])
          $fatal(1,"IDENTITY_COORD cycle=%0d idx=%0d got=%h,%h expected=%h,%h",cycle,head,o_sx_q16,o_sy_q16,q_x[head],q_y[head]);
        measured_latency=cycle-q_cycle[head];
        if(last_return==cycle-1) adjacent_returns=adjacent_returns+1;
        last_return=cycle;head=head+1;returned=returned+1;
      end else if(o_valid!==0) $fatal(1,"UNKNOWN_VALID");
      if(head<tail && cycle-q_cycle[head]>expected_latency) $fatal(1,"MISSING_OUTPUT");
    end
  end

  task init_frame;
    integer n;
    begin
      @(negedge clk); i_valid=0;i_frame_init=1;
      @(negedge clk); i_frame_init=0;
      n=0;
      while(o_init_done!==1 && n<=init_limit) begin
        // Valid before init_done must not be accepted.
        i_valid=1;i_u=17;i_v=23;
        @(negedge clk);n=n+1;
      end
      i_valid=0;
      if(o_init_done!==1) $fatal(1,"INIT_TIMEOUT");
    end
  endtask

  task send_pixels(input integer count,input integer gaps);
    integer j;
    begin
      for(j=0;j<count;j=j+1) begin
        @(negedge clk);
        i_valid=(gaps==0 || (j%5!=1 && j%7!=3));
        if(j%4==0) begin i_u=0;i_v=0;end
        else if(j%4==1) begin i_u=1919;i_v=1079;end
        else begin i_u=(j*73)%1920;i_v=(j*41)%1080;end
      end
      @(negedge clk);i_valid=0;
    end
  endtask

  task drain;
    begin
      repeat(expected_latency+4) @(negedge clk);
      if(head!=tail) $fatal(1,"DRAIN_INCOMPLETE");
    end
  endtask

  initial begin
    if($value$plusargs("LATENCY=%d",expected_latency)) begin end
    if($value$plusargs("INIT_LIMIT=%d",init_limit)) begin end
    repeat(3) @(negedge clk);rst_n=1;
    init_frame();send_pixels(96,0);drain();
    // Change the external coefficients without frame_init. Active frame stays identity.
    i_k1=-20000;i_k2=4000;i_aff_a11=60000;i_aff_tx=655360;
    send_pixels(97,1);drain();
    i_k1=0;i_k2=0;i_aff_a11=65536;i_aff_tx=0;i_aff_en=1;
    init_frame();send_pixels(64,0);drain();
    // A reset with pending outputs must discard only those pending tokens.
    send_pixels(5,0);
    @(negedge clk);rst_n=0;
    repeat(3) @(negedge clk);rst_n=1;
    init_frame();send_pixels(65,1);drain();
    if(init_count!=3 || adjacent_returns==0 || discarded!=5 || accepted!=returned+discarded)
      $fatal(1,"COVERAGE_OR_ACCOUNTING init=%0d adjacent=%0d discarded=%0d accepted=%0d returned=%0d",init_count,adjacent_returns,discarded,accepted,returned);
    $display("PROBE_PASS accepted=%0d returned=%0d reset_discarded=%0d latency_edge_distance=%0d adjacent_returns=%0d init_count=%0d",accepted,returned,discarded,measured_latency,adjacent_returns,init_count);
    $finish;
  end
  initial begin #200000; $fatal(1,"TB_TIMEOUT");end
endmodule
