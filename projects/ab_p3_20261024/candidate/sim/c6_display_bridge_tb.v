`timescale 1ns/1ps
// Accepted C6 logical requests with concurrent display traffic through the
// unchanged production broker. Words are checked independently by address.
module c6_display_bridge_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,req=0;
    reg [23:0] addr=0;
    reg [6:0] len=0;
    wire gnt,vld,last;
    wire [255:0] data;
    reg dreq=0;
    reg [27:0] daddr=0;
    reg [3:0] dlen=0;
    wire dgnt,dvld;
    wire [27:0] araddr;
    wire [3:0] arid,arlen;
    wire arvalid;
    integer tick=0;
    wire arready=tick%7!=0 && tick%19!=0;
    reg [255:0] rdata=0;
    reg rvalid=0,rlast=0,active=0;
    reg [3:0] rid=0;
    integer base,left,sent,delay_count,j;
    integer ctransactions=0,dtransactions=0,native_count=0;
    integer cbeats=0,dbeats=0,creturned=0,dreturned=0;
    integer cbase,dbase,clength,dlength,accept_tick;
    reg coutstanding=0,doutstanding=0,display_enable=0;
    reg stalled=0;
    reg [35:0] stalled_command;
    integer s,y,k,n,offset;
    corr_read_bridge dut(
        .clk(clk),.rst_n(rst_n),.corr_rd_req(req),.corr_rd_addr(addr),.corr_rd_len(len),
        .corr_rd_gnt(gnt),.corr_rd_vld(vld),.corr_rd_last(last),.corr_rd_data(data),
        .disp_araddr(daddr),.disp_arlen(dlen),.disp_arvalid(dreq),
        .disp_arready(dgnt),.disp_rvalid(dvld),.axi_araddr(araddr),.axi_arid(arid),
        .axi_arlen(arlen),.axi_arvalid(arvalid),.axi_arready(arready),
        .axi_rdata(rdata),.axi_rvalid(rvalid),.axi_rlast(rlast),.axi_rid(rid));
    function [31:0] word_at;
        input integer a;
        begin word_at=32'hA57312C9 ^ (a*32'h10201);end
    endfunction
    always @(negedge clk)begin
        if(rst_n)begin
            if(dreq && dgnt)dreq=0;
            if(display_enable && !dreq && !doutstanding && tick%83==0)begin
                // Deliberately straddle Columns in display traffic too.
                daddr=(4<<20)+(dtransactions*120+1008)%1036800;
                dlen=15;dreq=1;
            end
        end
    end
    always @(posedge clk)begin
        tick=tick+1;rvalid<=0;rlast<=0;
        if(rst_n)begin
            if(req && gnt)begin
                if(coutstanding || vld)$fatal(1,"logical overlap");
                if(addr[19:0]%960+(len+1)*8>960 || addr[2:0]!=0 || addr[23:20]>3)
                    $fatal(1,"C6 stimulus outside contract");
                coutstanding=1;cbase=addr;clength=len+1;creturned=0;
                accept_tick=tick;ctransactions=ctransactions+1;
            end
            if(dreq && dgnt)begin
                if(doutstanding)$fatal(1,"display logical overlap");
                doutstanding=1;dbase=daddr;dlength=dlen+1;dreturned=0;
                dtransactions=dtransactions+1;
            end
            if(stalled && (!arvalid || {araddr,arid,arlen}!==stalled_command))
                $fatal(1,"native command changed while blocked");
            stalled=arvalid && !arready;
            stalled_command={araddr,arid,arlen};
            if(arvalid && arready)begin
                if(active || arid>1 || araddr[2:0]!=0 || araddr[9:0]+(arlen+1)*8>1024)
                    $fatal(1,"native outstanding/alignment/Column violation");
                base=araddr;left=arlen+1;sent=0;rid<=arid;
                delay_count=(native_count%23==0)?64:1+native_count%5;
                active<=1;native_count=native_count+1;
            end else if(active)begin
                if(delay_count!=0)delay_count=delay_count-1;
                else if(tick%3==0)begin
                    for(j=0;j<8;j=j+1)rdata[j*32+:32]<=word_at(base+sent*8+j);
                    rvalid<=1;rlast<=left==1;sent=sent+1;left=left-1;
                    if(left==0)active<=0;
                end
            end
            if(vld)begin
                if(!coutstanding || tick<=accept_tick || last!==(creturned==clength-1))
                    $fatal(1,"logical correction return mismatch");
                for(j=0;j<8;j=j+1)
                    if(data[j*32+:32]!==word_at(cbase+creturned*8+j))
                        $fatal(1,"correction word order/data");
                creturned=creturned+1;cbeats=cbeats+1;
                if(last)coutstanding=0;
            end
            if(dvld)begin
                if(!doutstanding || dreturned>=dlength)$fatal(1,"display return overlap");
                for(j=0;j<8;j=j+1)
                    if(rdata[j*32+:32]!==word_at(dbase+dreturned*8+j))
                        $fatal(1,"display word order/data");
                dreturned=dreturned+1;dbeats=dbeats+1;
                if(dreturned==dlength)doutstanding=0;
            end
            if(vld && dvld)$fatal(1,"response routed to both owners");
        end
    end
    task read_block;
        input integer start_word,beats;
        begin
            @(negedge clk);addr=start_word;len=beats-1;req=1;
            @(posedge clk);while(!gnt)@(posedge clk);
            @(negedge clk);req=0;
            wait(!coutstanding);
        end
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;display_enable=1;
        for(s=0;s<4;s=s+1)begin
            // Every possible beat length that fits a 1920px row.
            for(n=1;n<=120;n=n+1)begin
                y=(n*37+s*19)%1080;
                offset=((n*17)%(121-n))*8;
                read_block((s<<20)+y*960+offset,n);
            end
            // All 64px segments of every source row and all source slots.
            for(y=0;y<1080;y=y+1)
                for(k=0;k<30;k=k+1)read_block((s<<20)+y*960+k*32,4);
            read_block((s<<20)+1079*960,120);
        end
        @(negedge clk);display_enable=0;
        wait(!doutstanding && !dreq && !active);
        repeat(8)@(negedge clk);
        if(ctransactions!=130084 || dtransactions<100 || cbeats!=547920)
            $fatal(1,"coverage totals c=%0d d=%0d cb=%0d",ctransactions,dtransactions,cbeats);
        $display("C6_DISPLAY_BRIDGE PASS correction_txn=%0d correction_beats=%0d display_txn=%0d display_beats=%0d native=%0d max_native_outstanding=1",ctransactions,cbeats,dtransactions,dbeats,native_count);
        $finish;
    end
    initial begin #300000000;$fatal(1,"C6 display timeout");end
endmodule
