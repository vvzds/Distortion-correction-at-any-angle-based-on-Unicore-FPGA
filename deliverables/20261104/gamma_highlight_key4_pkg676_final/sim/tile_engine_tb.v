`timescale 1ns/1ps
module tile_engine_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_update=0;
    reg [511:0] cfg;reg [31:0] config_words[0:15];
    wire busy,src_req,src_rel,rd_req,wr_req,slot_req,commit,published;
    wire [23:0] rd_addr,wr_addr;wire [6:0] rd_len;wire [31:0] wr_data;
    wire [31:0] frames,cycles,rd_wait,wr_wait,read_beats,invalid,overflow;
    wire fault;wire [1:0] gamma_mode;
    wire [511:0] published_cfg;
    reg src_gnt=0;
    wire wr_gnt,writer_idle,pack_error;
    wire slot_gnt=slot_req && writer_idle;
    reg rd_gnt=0,rd_valid=0,rd_last=0;
    reg [255:0] rd_data;
    tile_engine dut(clk,rst_n,frame_update,cfg,1'b0,busy,src_req,src_gnt,2'd1,src_rel,
        rd_req,rd_addr,rd_len,rd_gnt,rd_valid,rd_last,rd_data,
        slot_req,slot_gnt,3'd4,wr_req,wr_addr,wr_data,wr_gnt,commit,published,
        frames,cycles,rd_wait,wr_wait,read_beats,invalid,overflow,fault,gamma_mode,published_cfg);
    wire [23:0] awaddr;wire [3:0] awlen;
    wire awvalid;reg awready=0,wpull=0,wlast=0;wire [255:0] wdata;
    tile_write_pack pack(clk,rst_n,slot_gnt,3'd4,wr_req,wr_addr,wr_data,wr_gnt,commit,
                         writer_idle,published,pack_error,awaddr,awlen,awvalid,awready,wdata,wpull,wlast);
    function [15:0] source_pixel;
        input integer x,y;
        reg [31:0] p;
        begin p=((x&31)<<11)|((y&63)<<5)|((x^y)&31);source_pixel=p[15:0];end
    endfunction
    reg [15:0] golden[0:2073599];
    reg seen[0:2073599];
    reg [1023:0] config_file,golden_file,result_file;
    integer latency=24,gap=4,i,j,received=0,wall_cycles=0;
    integer rdelay=0,rremain=0,raddress=0,rrow,rx;
    integer wdelay=0,wremain=0,waddress=0,wy,wx,idx;
    reg [31:0] random_state=32'h10803055;
    initial begin
        if(!$value$plusargs("CONFIG=%s",config_file)) $fatal(1,"CONFIG");
        if(!$value$plusargs("GOLDEN=%s",golden_file)) $fatal(1,"GOLDEN");
        if(!$value$plusargs("RESULT=%s",result_file)) result_file="result.json";
        i=$value$plusargs("LATENCY=%d",latency);i=$value$plusargs("GAP=%d",gap);
        $readmemh(config_file,config_words);$readmemh(golden_file,golden);
        for(i=0;i<16;i=i+1) cfg[i*32+:32]=config_words[i];
        for(i=0;i<2073600;i=i+1) seen[i]=0;
        repeat(8) @(negedge clk);rst_n=1;
        repeat(4) @(negedge clk);frame_update=1;
        @(negedge clk);frame_update=0;
    end
    // Sample transactions on posedge and drive response signals on negedge.
    always @(posedge clk) if(rst_n) begin
        wall_cycles=wall_cycles+1;
        if(rd_req && rd_gnt) begin
            if(rremain) $fatal(1,"Overlapping read request");
            raddress=rd_addr;rremain=rd_len+1;rdelay=latency;
        end
        if(rd_valid) begin rremain=rremain-1;raddress=raddress+8;end
        if(awvalid && awready) begin
            if(wremain) $fatal(1,"Overlapping native write");
            if(awlen!=3) $fatal(1,"Packet length");
            waddress=awaddr;wremain=4;wdelay=6;
        end
        if(wpull) begin
            wy=1079-((waddress&20'hfffff)/960);
            wx=((waddress&20'hfffff)%960)*2;
            if(wy<0 || wy>=1080 || wx>1904) $fatal(1,"Write bounds");
            for(j=0;j<16;j=j+1) begin
                idx=wy*1920+wx+j;
                if(seen[idx]) $fatal(1,"Duplicate output %0d,%0d",wx+j,wy);
                if(wdata[j*16+:16]!==golden[idx])
                    $fatal(1,"Pixel mismatch at %0d,%0d got %h expected %h",wx+j,wy,wdata[j*16+:16],golden[idx]);
                seen[idx]=1;received=received+1;
            end
            wremain=wremain-1;waddress=waddress+8;
        end
        if(fault || pack_error || overflow) $fatal(1,"Protocol/patch fault");
        if(published) begin
            if(received!=2073600) $fatal(1,"Pixel count %0d",received);
            #12;
            i=$fopen(result_file,"w");
            $fdisplay(i,"{\"cycles\":%0d,\"read_wait\":%0d,\"write_wait\":%0d,\"read_beats\":%0d,\"invalid_pixels\":%0d,\"pixels_checked\":%0d,\"latency\":%0d,\"gap\":%0d}",cycles,rd_wait,wr_wait,read_beats,invalid,received,latency,gap);
            $fclose(i);
            if(cycles>4166666) $fatal(1,"30fps budget exceeded: %0d",cycles);
            $display("PASS full frame pixels=%0d cycles=%0d fps=%f",received,cycles,125000000.0/cycles);$finish;
        end
        if(wall_cycles>12000000) $fatal(1,"Timeout fs=%0d ls=%0d ws=%0d",dut.fs,dut.ls,dut.ws);
    end
    always @(negedge clk) if(rst_n) begin
        random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
        src_gnt=src_req;
        rd_gnt=(rremain==0);
        rd_valid=0;rd_last=0;
        if(rdelay>0) rdelay=rdelay-1;
        else if(rremain>0 && (gap==0 || random_state%gap!=0)) begin
            rd_valid=1;rd_last=(rremain==1);
            rrow=1079-((raddress&20'hfffff)/960);rx=((raddress&20'hfffff)%960)*2;
            for(i=0;i<16;i=i+1) rd_data[i*16+:16]=source_pixel(rx+i,rrow);
        end
        awready=(wremain==0 && random_state[3:2]!=0);
        wpull=0;wlast=0;
        if(wdelay>0) wdelay=wdelay-1;
        else if(wremain>0 && random_state[6:5]!=0) begin wpull=1;wlast=(wremain==1);end
    end
endmodule
