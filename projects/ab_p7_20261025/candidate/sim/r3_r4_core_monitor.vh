// R3/R4 observational assertions only: never drive DUT internals.
integer mon_cycle=0,mon_outstanding=0,mon_accepted=0,mon_returned=0;
integer mon_accept_cycle=0,mon_previous_return=0,mon_index=0,mon_wait=0;
integer mon_first_min=2147483647,mon_first_max=0;
integer mon_gap_min=2147483647,mon_gap_max=0;
integer mon_grant_min=2147483647,mon_grant_max=0;
integer mon_clears=0,mon_busy_starts=0,mon_delta;
always @(posedge clk) begin
    if(rst_n)begin
        mon_cycle=mon_cycle+1;
        if(start && busy)mon_busy_starts=mon_busy_starts+1;
        if(rd_req && !rd_gnt)mon_wait=mon_wait+1;
        if(rd_req && rd_gnt)begin
            if(mon_outstanding!=0)$fatal(1,"R3 multiple accepted logical reads");
            mon_outstanding=len+1;mon_index=0;mon_accept_cycle=mon_cycle;
            mon_accepted=mon_accepted+1;
            if(mon_wait<mon_grant_min)mon_grant_min=mon_wait;
            if(mon_wait>mon_grant_max)mon_grant_max=mon_wait;
            mon_wait=0;
        end
        if(rd_vld)begin
            if(mon_outstanding<=0 || rd_last!==(mon_outstanding==1))
                $fatal(1,"R3 unattributed response or LAST");
            mon_delta=mon_index==0?mon_cycle-mon_accept_cycle:mon_cycle-mon_previous_return;
            if(mon_index==0)begin
                if(mon_delta<mon_first_min)mon_first_min=mon_delta;
                if(mon_delta>mon_first_max)mon_first_max=mon_delta;
            end else begin
                if(mon_delta<mon_gap_min)mon_gap_min=mon_delta;
                if(mon_delta>mon_gap_max)mon_gap_max=mon_delta;
            end
            mon_previous_return=mon_cycle;mon_index=mon_index+1;
            mon_outstanding=mon_outstanding-1;mon_returned=mon_returned+1;
        end
        if(dut.u_cache.i_frame_clear)begin
            if(mon_outstanding!=0 || rd_vld || rd_req || dut.u_cache.load_active ||
               dut.u_cache.first_pending || dut.u_cache.output_pending ||
               dut.u_cache.i_sample_req_q || dut.sample_pipe!=0)
                $fatal(1,"R3 frame-clear overlaps accepted read/sample pipeline");
            mon_clears=mon_clears+1;
        end
        if(rel && (mon_outstanding!=0 || rd_vld || rd_req ||
                   dut.u_cache.load_active || dut.u_cache.fetch_count!=0 ||
                   dut.u_cache.tag_pending!=0 || dut.u_cache.o_lookup_busy))
            $fatal(1,"R3 release before all accepted/queued reads drained");
    end
end
