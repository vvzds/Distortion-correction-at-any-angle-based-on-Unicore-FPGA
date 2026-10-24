`timescale 1ns/1ps
// Real UART -> core -> gamma -> rect_wr_if with production read broker and
// concurrent display traffic. Uses source/golden vectors in memory row order.
module c6_host_arb_tb;
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
    wire slotgnt,pub;
    wire [2:0] target;
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
    wire wrgnt;
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
    // Production slot allocation, packet drain and raw/correction arbitration.
    wire writer_idle,pack_error,pawvalid,pawready,pwpull,pwlast;
    wire [23:0] pawaddr;
    wire [3:0] pawlen;
    wire [255:0] pwdata;
    wire [1:0] display_bank;
    wire display_valid;
    wire display_start=cycles%100003==0;
    wire raw_ready,raw_pull,raw_last;
    reg raw_req=0,raw_accepted=0;
    reg [27:0] raw_addr=0;
    integer raw_index=0,raw_transactions=0,raw_done=0;
    wire [31:0] raw_word=32'hCA000000+raw_addr+raw_index*8;
    wire [255:0] raw_data={8{raw_word}};
    wire awvalid,awready;
    wire [27:0] awaddr;
    wire [3:0] awlen,awid;
    wire [255:0] wdata;
    wire [31:0] wstrb;
    reg wactive=0;
    integer wleft=0,wdelay=0,woffset=0,write_beats=0,write_transactions=0;
    reg [3:0] wid=0;
    reg [27:0] native_write_addr=0;
    wire wpull=wactive && wdelay==0 && cycles%5!=0;
    wire wlast=wpull && wleft==1;
    assign awready=!wactive && cycles%7!=0;
    integer native_output_index,wl,commits=0,pub_cycle=0;
    reg commit_seen=0;
    reg [2:0] allocated=0;
    reg awblocked=0;
    reg [35:0] awprevious=0;
    corr_slot_ctrl slot_ctrl(
        .clk(clk),.rst_n(rst_n),.rd_start(display_start),
        .corr_wr_slot_req(slotreq),.writer_idle(writer_idle),.publish(pub),
        .corr_wr_slot_gnt(slotgnt),.corr_wr_slot(target),
        .rd_bank(display_bank),.display_valid(display_valid));
    corr_write_pack pack(
        .clk(clk),.rst_n(rst_n),.begin_frame(slotgnt),.frame_slot(target),
        .corr_wr_req(wrreq),.corr_wr_addr(wraddr),.corr_wr_data(wrdata),
        .corr_wr_gnt(wrgnt),.corr_wr_commit(commit),
        .frame_idle(writer_idle),.publish(pub),.protocol_error(pack_error),
        .awaddr(pawaddr),.awlen(pawlen),.awvalid(pawvalid),.awready(pawready),
        .wdata(pwdata),.wpull(pwpull),.wlast(pwlast));
    corr_write_arb write_arb(
        .clk(clk),.rst_n(rst_n),.raw_awaddr(raw_addr),.raw_awlen(4'd15),
        .raw_awid(4'd0),.raw_awvalid(raw_req),.raw_awready(raw_ready),
        .raw_wpull(raw_pull),.raw_wlast(raw_last),.raw_wdata(raw_data),
        .raw_wstrb(32'hffffffff),.corr_awaddr(pawaddr),.corr_awlen(pawlen),
        .corr_awvalid(pawvalid),.corr_awready(pawready),
        .corr_wpull(pwpull),.corr_wlast(pwlast),.corr_wdata(pwdata),
        .axi_awaddr(awaddr),.axi_awlen(awlen),.axi_awid(awid),
        .axi_awvalid(awvalid),.axi_awready(awready),
        .axi_wdata(wdata),.axi_wstrb(wstrb),.axi_wpull(wpull),.axi_wlast(wlast));
    always @(negedge clk)if(rst_n)begin
        if(raw_accepted)raw_req=0;
        if(display_enable && !raw_req && raw_transactions==raw_done && cycles%173==0)begin
            raw_addr=(2<<20)+1008;raw_req=1;
        end
    end
    always @(posedge clk)if(rst_n)begin
        raw_accepted<=raw_req && raw_ready;
        if(raw_req && raw_ready)begin raw_index=0;raw_transactions=raw_transactions+1;end
        if(raw_pull)begin raw_index<=raw_index+1;if(raw_last)raw_done=raw_done+1;end
        if(slotgnt)begin
            if(display_valid && target[1:0]==display_bank)$fatal(1,"allocated displayed slot");
            allocated=target;
        end
        if(awblocked && (!awvalid || {awaddr,awlen,awid}!==awprevious))
            $fatal(1,"native AW changed during stall");
        awblocked=awvalid&&!awready;awprevious={awaddr,awlen,awid};
        if(awvalid && awready)begin
            if(wactive || awaddr[9:0]+(awlen+1)*8>1024)$fatal(1,"native AW overlap/Column");
            wactive<=1;wleft=awlen+1;wdelay=4;wid<=awid;
            native_write_addr<=awaddr;write_transactions=write_transactions+1;
        end else if(wactive)begin
            if(wdelay>0)wdelay<=wdelay-1;
            else if(wpull)begin
                if(wstrb!==32'hffffffff)$fatal(1,"native write mask");
                if(wid==1)begin
                    if(native_write_addr[23:20]!=allocated ||
                       native_write_addr[19:0]!=write_beats*8)
                        $fatal(1,"native corrected write address/order");
                    native_output_index=write_beats*16;
                    for(wl=0;wl<16;wl=wl+1)
                        if(wdata[16*wl+:16]!==expected[native_output_index+wl])
                            $fatal(1,"native corrected pixel mismatch n=%0d",native_output_index+wl);
                    write_beats=write_beats+1;
                end else if(wdata!=={8{32'hCA000000+native_write_addr}})
                    $fatal(1,"raw write ownership/data");
                native_write_addr<=native_write_addr+8;
                wleft<=wleft-1;if(wleft==1)wactive<=0;
            end
        end
        if(pack_error)$fatal(1,"host pack protocol error");
        if(commit)begin
            if(commit_seen)$fatal(1,"double commit");commit_seen=1;commits=commits+1;
        end
        if(pub)begin
            if(!commit_seen || !writer_idle || pack.packet_ready || write_beats!=129600)
                $fatal(1,"publication before full native write drain");
            if(cycles<=done_cycle)$fatal(1,"commit/publish not distinguished");
            published=1;pub_cycle=cycles;
        end
    end
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
        cycles<=cycles+1;rvalid<=0;rlast<=0;
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

        if(wrblocked && (!wrreq || {wraddr,wrdata}!==wrprevious))$fatal(1,"blocked write changed");
        wrblocked=wrreq&&!wrgnt;wrprevious={wraddr,wrdata};
        if(wrreq && wrgnt)begin
            if(wraddr!==((allocated<<20)+words) || words>=1036800 ||
               wrdata!=={expected[2*words+1],expected[2*words]})
                $fatal(1,"corrected DDR word mismatch word=%0d addr=%h got=%h",words,wraddr,wrdata);
            words=words+1;
            if(words%259200==0)
                $display("C6_SUBSYSTEM_PROGRESS words=%0d cycles=%0d reads=%0d display=%0d",words,cycles,segments,dtransactions);
        end
        if(commit)begin
            if(words!=1036800 || published!=0)$fatal(1,"bad commit");
            done_cycle=cycles;
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
        if(dtransactions<100 || raw_done<100 || commits!=1 || write_beats!=129600)
            $fatal(1,"host arbitration coverage incomplete");
        wait(display_valid);repeat(2)@(negedge clk);
        if(display_bank!==allocated[1:0])$fatal(1,"published display slot not selected");
        $display("HOST_ARBITRATION native_corrected_beats=%0d raw_txn=%0d native_write_txn=%0d commit_to_publish_cycles=%0d",
                 write_beats,raw_done,write_transactions,pub_cycle-done_cycle);
        $display("C6_HOST_ARB PASS mode=%0d pixels=2073600 words=%0d logical_reads=%0d display_txn=%0d cycles=%0d fps_125MHz=%f",mode,words,segments,dtransactions,done_cycle-frame_start_cycle,125000000.0/(done_cycle-frame_start_cycle));
        $finish;
    end
    initial begin #200000000;$fatal(1,"subsystem timeout words=%0d",words);end
endmodule
