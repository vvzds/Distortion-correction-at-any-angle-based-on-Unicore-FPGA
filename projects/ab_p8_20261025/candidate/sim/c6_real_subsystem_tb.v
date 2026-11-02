`timescale 1ns/1ps
// Real UART -> core -> gamma -> rect_wr_if with production read broker and
// concurrent display traffic. Uses source/golden vectors in memory row order.
module c6_real_subsystem_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,rx=1;
    wire tx,hold_req,rel,req,gnt,vld,last;
    wire [23:0] addr;
    wire [6:0] len;
    wire [255:0] data;
    reg held=0;
    wire slotreq,wrreq,commit;
    wire [23:0] wraddr;
    wire [31:0] wrdata;
    reg slotgnt=0,pub=0;
    reg [2:0] target=4;
    reg [255:0] source_words[0:129599];
    reg [15:0] expected[0:2073599];
    reg [7:0] command[0:36];
    reg [7:0] stop_command[0:36];
    integer mode=1,cycles=0,native_count=0,segments=0,words=0,published=0;
    integer base,left,sent,delay_count,j;
    reg [255:0] rdata=0;
    reg rvalid=0,rlast=0,active=0;
    reg [3:0] rid=0;
    wire [27:0] araddr;
    wire [3:0] arid,arlen;
    wire arvalid;
    wire arready=cycles%7!=0;
    reg dreq=0,doutstanding=0,display_enable=1;
    reg daccepted=0;
    reg [27:0] daddr=0;
    wire dgnt,dvld;
    integer dreturned=0,dtransactions=0,dwords=0,dbase=0;
    wire wrgnt=rst_n && cycles%5!=0;
    reg wrblocked=0;
    reg [55:0] wrprevious=0;
    integer frame_start_cycle=0,done_cycle=0,uart_index,vector_fd,stop_checksum;
    integer hold_count=0,release_count=0;
    corr_top #(.CLK_FREQ(12500000)) dut(
        .clk(clk),.rst_n(rst_n),.i_uart_rx(rx),.o_uart_tx(tx),
        .i_frame_wcnt(2'd3),.i_frame_update(1'b0),
        .o_corr_src_hold_req(hold_req),.i_corr_src_hold_gnt(held),
        .i_corr_src_slot(2'd3),.o_corr_src_rel(rel),
        .o_corr_rd_req(req),.o_corr_rd_addr(addr),.o_corr_rd_len(len),
        .i_corr_rd_gnt(gnt),.i_corr_rd_vld(vld),.i_corr_rd_data(data),.i_corr_rd_last(last),
        .o_corr_wr_slot_req(slotreq),.i_corr_wr_slot_gnt(slotgnt),
        .i_corr_wr_slot(target),.o_corr_wr_commit(commit),
        .o_corr_wr_req(wrreq),.o_corr_wr_addr(wraddr),.o_corr_wr_data(wrdata),
        .i_corr_wr_gnt(wrgnt),.i_corr_pub_pulse(pub));
    corr_read_bridge bridge(
        .clk(clk),.rst_n(rst_n),.corr_rd_req(req),.corr_rd_addr(addr),.corr_rd_len(len),
        .corr_rd_gnt(gnt),.corr_rd_vld(vld),.corr_rd_last(last),.corr_rd_data(data),
        .disp_araddr(daddr),.disp_arlen(4'd15),.disp_arvalid(dreq),
        .disp_arready(dgnt),.disp_rvalid(dvld),.axi_araddr(araddr),.axi_arid(arid),
        .axi_arlen(arlen),.axi_arvalid(arvalid),.axi_arready(arready),
        .axi_rdata(rdata),.axi_rvalid(rvalid),.axi_rlast(rlast),.axi_rid(rid));
    always @(negedge clk)if(rst_n)begin
        if(daccepted)dreq=0;
        if(display_enable && !dreq && !doutstanding && cycles%137==0)begin
            daddr=(4<<20)+(dtransactions*120+1008)%1036800;dreq=1;
        end
    end
    always @(posedge clk)if(rst_n)begin
        // NBA keeps combinational ready/stall inputs stable at the sampling edge.
        cycles<=cycles+1;rvalid<=0;rlast<=0;slotgnt<=0;pub<=0;
        daccepted<=dreq && dgnt;
        if(hold_req && !held)begin
            held<=1;frame_start_cycle=cycles;hold_count=hold_count+1;
            if(hold_count!=1)$fatal(1,"unexpected second source frame");
        end
        if(rel)begin
            if((active && rid==1) || vld || bridge.corr_busy)
                $fatal(1,"release with pending correction reads");
            held<=0;
            release_count=release_count+1;
        end
        if(req && gnt)begin
            if(!held || addr[23:20]!=3 || addr[19:0]%960+(len+1)*8>960 ||
               (mode?len!=3:len!=119))$fatal(1,"C6 source contract");
            segments=segments+1;
        end
        if(dreq && dgnt)begin
            if(doutstanding)$fatal(1,"display logical overlap");
            doutstanding=1;dreturned=0;dbase=daddr;dtransactions=dtransactions+1;
        end
        if(arvalid && arready)begin
            if(active || araddr[9:0]+(arlen+1)*8>1024)$fatal(1,"native overlap/Column");
            base=araddr;left=arlen+1;sent=0;rid<=arid;
            delay_count=2+native_count%5;native_count=native_count+1;active<=1;
        end else if(active)begin
            if(delay_count>0)delay_count=delay_count-1;
            else if(cycles%11!=0)begin
                rvalid<=1;rlast<=left==1;
                if(rid==1)rdata<=source_words[((base&1048575)>>3)+sent];
                else for(j=0;j<8;j=j+1)rdata[32*j+:32]<=32'h81a71235^(base+sent*8+j);
                sent=sent+1;left=left-1;if(left==0)active<=0;
            end
        end
        if(dvld)begin
            if(!doutstanding)$fatal(1,"unexpected display return");
            for(j=0;j<8;j=j+1)if(rdata[32*j+:32] !== (32'h81a71235^(dbase+dreturned*8+j)))
                $fatal(1,"display data mismatch");
            dreturned=dreturned+1;dwords=dwords+1;if(dreturned==16)doutstanding=0;
        end
        if(slotreq && !slotgnt)slotgnt<=1;
        if(wrblocked && (!wrreq || {wraddr,wrdata}!==wrprevious))$fatal(1,"blocked write changed");
        wrblocked=wrreq&&!wrgnt;wrprevious={wraddr,wrdata};
        if(wrreq && wrgnt)begin
            if(wraddr!==((4<<20)+words) || words>=1036800 ||
               wrdata!=={expected[2*words+1],expected[2*words]})
                $fatal(1,"corrected DDR word mismatch word=%0d addr=%h got=%h",words,wraddr,wrdata);
            words=words+1;
            if(words%259200==0)
                $display("C6_SUBSYSTEM_PROGRESS words=%0d cycles=%0d reads=%0d display=%0d",words,cycles,segments,dtransactions);
        end
        if(commit)begin
            if(words!=1036800 || published!=0)$fatal(1,"bad commit");
            pub<=1;published=1;done_cycle=cycles;
        end
        if(dut.u_core.load_error || dut.u_wr_if.fault)$fatal(1,"subsystem fault");
        if(dut.w_frame_busy && (dut.w_stat_line_stats_valid!==(mode==0)))$fatal(1,"statistics mode");
    end
    task uart_byte;
        input [7:0] b;
        integer k;
        begin
            @(negedge clk);rx=0;repeat(108)@(negedge clk);
            for(k=0;k<8;k=k+1)begin rx=b[k];repeat(108)@(negedge clk);end
            rx=1;repeat(108)@(negedge clk);
        end
    endtask
    initial begin
        if(!$value$plusargs("MODE=%d",mode))mode=1;
        // Fail immediately on an incorrect launch directory instead of running
        // millions of cycles with uninitialized parameters or pixel vectors.
        vector_fd=$fopen("vectors/source_words_1.hex","r");
        if(!vector_fd)$fatal(1,"missing source vector: launch from verification_data");
        $fclose(vector_fd);
        vector_fd=$fopen(mode?"vectors/real_pixels_1.hex":"vectors/identity_pixels.hex","r");
        if(!vector_fd)$fatal(1,"missing expected pixel vector");
        $fclose(vector_fd);
        vector_fd=$fopen(mode?"vectors/real_uart_bytes.hex":"vectors/identity_uart_bytes.hex","r");
        if(!vector_fd)$fatal(1,"missing UART command vector");
        $fclose(vector_fd);
        $readmemh("vectors/source_words_1.hex",source_words);
        if(mode)begin $readmemh("vectors/real_pixels_1.hex",expected);$readmemh("vectors/real_uart_bytes.hex",command);end
        else begin $readmemh("vectors/identity_pixels.hex",expected);$readmemh("vectors/identity_uart_bytes.hex",command);end
        $display("C6_SUBSYSTEM_START mode=%0d vectors_loaded=1",mode);
        repeat(4)@(negedge clk);rst_n=1;
        for(uart_index=0;uart_index<37;uart_index=uart_index+1)uart_byte(command[uart_index]);
        repeat(100)@(negedge clk);
        if(!dut.w_params_valid)$fatal(1,"UART calibration command not accepted");
        $display("C6_SUBSYSTEM_UART_ACCEPTED mode=%0d",mode);
        // Stage an invalid fx through the real UART while the first frame is
        // busy. It takes effect at the frame gap and prevents free-run from
        // clearing the just-completed frame counters before final assertions.
        if(!dut.w_frame_busy)$fatal(1,"first frame not running");
        for(uart_index=0;uart_index<37;uart_index=uart_index+1)
            stop_command[uart_index]=command[uart_index];
        for(uart_index=4;uart_index<8;uart_index=uart_index+1)stop_command[uart_index]=0;
        stop_checksum=0;
        for(uart_index=4;uart_index<36;uart_index=uart_index+1)
            stop_checksum=stop_checksum+stop_command[uart_index];
        stop_command[36]=stop_checksum;
        for(uart_index=0;uart_index<37;uart_index=uart_index+1)
            uart_byte(stop_command[uart_index]);
        if(!dut.w_params_valid)$fatal(1,"shadow parameters changed during busy frame");
        wait(published==1);@(negedge clk);display_enable=0;
        wait(!dut.w_frame_busy);repeat(10)@(negedge clk);
        if(dut.w_params_valid || held || hold_req || req || release_count!=1 || hold_count!=1)
            $fatal(1,"single-frame stop/drain failed");
        if(mode && segments!=dut.w_stat_seg_loads)$fatal(1,"accepted segment counter");
        if(mode && (dut.w_stat_line_loads!=0 || dut.w_stat_line_hits!=0))$fatal(1,"old stats interpreted");
        if(dtransactions<100)$fatal(1,"no display concurrency");
        $display("C6_REAL_SUBSYSTEM PASS mode=%0d pixels=2073600 words=%0d logical_reads=%0d display_txn=%0d cycles=%0d fps_125MHz=%f",mode,words,segments,dtransactions,done_cycle-frame_start_cycle,125000000.0/(done_cycle-frame_start_cycle));
        $finish;
    end
    initial begin #200000000;$fatal(1,"subsystem timeout words=%0d",words);end
endmodule
