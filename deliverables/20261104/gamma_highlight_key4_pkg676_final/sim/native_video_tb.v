`timescale 1ns/1ps
// End-to-end correction through the production DDR brokers, with concurrent
// nominal-1080p30 capture writes and display reads. One shared data bus slot per
// clock; random direction choice, first-read latency and random data gaps.
module native_video_tb;
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
    wire rd_gnt,rd_valid,rd_last;wire [255:0] rd_data;
    tile_engine dut(clk,rst_n,frame_update,cfg,1'b0,busy,src_req,src_gnt,2'd1,src_rel,
        rd_req,rd_addr,rd_len,rd_gnt,rd_valid,rd_last,rd_data,
        slot_req,slot_gnt,3'd4,wr_req,wr_addr,wr_data,wr_gnt,commit,published,
        frames,cycles,rd_wait,wr_wait,read_beats,invalid,overflow,fault,gamma_mode,published_cfg);
    wire [23:0] cw_addr;wire [3:0] cw_len;wire cw_valid,cw_ready,cw_pull,cw_last;
    wire [255:0] cw_data;
    tile_write_pack pack(clk,rst_n,slot_gnt,3'd4,wr_req,wr_addr,wr_data,wr_gnt,commit,
        writer_idle,published,pack_error,cw_addr,cw_len,cw_valid,cw_ready,cw_data,cw_pull,cw_last);
    // Background command generators keep VALID asserted until accepted.
    reg disp_valid=0,capture_valid=0;
    reg [27:0] disp_address=28'h0400000,capture_address=0;
    wire disp_ready,disp_rvalid,capture_ready,capture_pull,capture_last;
    wire [27:0] araddr,awaddr;wire [3:0] arlen,arid,awlen,awid;
    wire arvalid,awvalid;reg arready=0,awready=0;
    reg [255:0] rdata;reg rvalid=0,rlast=0;reg [3:0] rid=0;
    wire [255:0] wdata;wire [31:0] wstrb;reg wpull=0,wlast=0;
    corr_read_bridge reader(clk,rst_n,rd_req,rd_addr,rd_len,rd_gnt,rd_valid,rd_last,rd_data,
        disp_address,4'd15,disp_valid,disp_ready,disp_rvalid,
        araddr,arid,arlen,arvalid,arready,rdata,rvalid,rlast,rid);
    corr_write_arb writer(clk,rst_n,capture_address,4'd15,4'd0,capture_valid,
        capture_ready,capture_pull,capture_last,256'd0,32'hffffffff,
        cw_addr,cw_len,cw_valid,cw_ready,cw_pull,cw_last,cw_data,
        awaddr,awlen,awid,awvalid,awready,wdata,wstrb,wpull,wlast);
    reg [15:0] source_image[0:2073599];reg real_source=0;
    reg [1023:0] source_file;
    function [15:0] source_pixel;
        input integer x,y;reg [31:0] p;
        begin p=((x&31)<<11)|((y&63)<<5)|((x^y)&31);
            source_pixel=real_source?source_image[y*1920+x]:p[15:0];end
    endfunction
    reg [15:0] golden[0:2073599];reg seen[0:2073599];
    reg [1023:0] config_file,golden_file,result_file,config2_file,golden2_file;
    reg [31:0] config2_words[0:15];
    integer completed_frames=0,target_frames=1;
    integer latency=24,gap=4,period=514,i,j,received=0,wall_cycles=0;
    integer rdelay=0,rremain=0,raddress=0,rrow,rx,read_id=0;
    integer wdelay=0,wremain=0,waddress=0,write_id=0,wy,wx,idx;
    integer disp_counter=0,capture_counter=257,display_beats=0,capture_beats=0;
    reg [31:0] random_state=32'h10803055;
    initial begin
        if(!$value$plusargs("CONFIG=%s",config_file)) $fatal(1,"CONFIG");
        if(!$value$plusargs("GOLDEN=%s",golden_file)) $fatal(1,"GOLDEN");
        if(!$value$plusargs("RESULT=%s",result_file)) result_file="native_result.json";
        i=$value$plusargs("LATENCY=%d",latency);i=$value$plusargs("GAP=%d",gap);
        i=$value$plusargs("PERIOD=%d",period);
        $readmemh(config_file,config_words);$readmemh(golden_file,golden);
        if($value$plusargs("SOURCE=%s",source_file)) begin $readmemh(source_file,source_image);real_source=1;end
        if($value$plusargs("CONFIG2=%s",config2_file)) begin
            if(!$value$plusargs("GOLDEN2=%s",golden2_file)) $fatal(1,"GOLDEN2");
            $readmemh(config2_file,config2_words);target_frames=2;
        end
        for(i=0;i<16;i=i+1) cfg[i*32+:32]=config_words[i];
        for(i=0;i<2073600;i=i+1) seen[i]=0;
        repeat(8) @(negedge clk);rst_n=1;
        repeat(4) @(negedge clk);frame_update=1;
        @(negedge clk);frame_update=0;
        if(target_frames==2) begin
            wait(dut.fs==2);repeat(100) @(negedge clk);
            // Deliberately change the live bus during an active frame. The
            // frame-latched datapath must finish using its original matrix.
            for(i=0;i<16;i=i+1)cfg[i*32+:32]=config2_words[i];
            wait(published);@(negedge clk);frame_update=1;
            @(negedge clk);frame_update=0;
        end
    end
    always @(posedge clk) if(rst_n) begin
        wall_cycles=wall_cycles+1;
        disp_counter=disp_counter+1;capture_counter=capture_counter+1;
        if(disp_counter>=period) begin
            if(disp_valid) $fatal(1,"HDMI command deadline missed");
            disp_valid<=1;disp_counter=0;
        end
        if(capture_counter>=period) begin
            if(capture_valid) $fatal(1,"Camera command deadline missed");
            capture_valid<=1;capture_counter=0;
        end
        // Delay generator deassertions to avoid races with broker posedge logic.
        if(disp_valid && disp_ready) begin
            disp_valid<=0;
            disp_address<=disp_address[19:0]>=1036672 ? 28'h0400000 : disp_address+128;
        end
        if(capture_valid && capture_ready) begin
            capture_valid<=0;
            capture_address<=capture_address>=1036672 ? 0 : capture_address+128;
        end
        if(arvalid && arready) begin
            if(rremain) $fatal(1,"Overlapping native read");
            if(araddr[9:0]+(arlen+1)*8>1024) $fatal(1,"Read column crossing");
            raddress=araddr;rremain=arlen+1;rdelay=latency;read_id=arid;
        end
        if(rvalid) begin
            if(read_id==0) display_beats=display_beats+1;
            rremain=rremain-1;raddress=raddress+8;
        end
        if(awvalid && awready) begin
            if(wremain) $fatal(1,"Overlapping native write");
            if(awaddr[9:0]+(awlen+1)*8>1024) $fatal(1,"Write column crossing");
            waddress=awaddr;wremain=awlen+1;wdelay=6;write_id=awid;
        end
        if(wpull) begin
            if(write_id==1) begin
                wy=1079-((waddress&20'hfffff)/960);wx=((waddress&20'hfffff)%960)*2;
                if(wy<0 || wy>=1080 || wx>1904) $fatal(1,"Write bounds");
                for(j=0;j<16;j=j+1) begin
                    idx=wy*1920+wx+j;
                    if(seen[idx]) $fatal(1,"Duplicate output %0d,%0d",wx+j,wy);
                    if(wdata[j*16+:16]!==golden[idx])
                        $fatal(1,"Pixel mismatch at %0d,%0d got %h expected %h",wx+j,wy,wdata[j*16+:16],golden[idx]);
                    seen[idx]=1;received=received+1;
                end
            end else capture_beats=capture_beats+1;
            wremain=wremain-1;waddress=waddress+8;
        end
        if(fault || pack_error || overflow) $fatal(1,"Protocol/patch fault");
        if(published) begin
            if(received!=2073600) $fatal(1,"Pixel count %0d",received);
            if(display_beats<wall_cycles/period*16-128) $fatal(1,"Insufficient display traffic %0d",display_beats);
            if(capture_beats<wall_cycles/period*16-128) $fatal(1,"Insufficient capture traffic %0d",capture_beats);
            #12;
            if(cycles>4166666) $fatal(1,"30fps budget exceeded: %0d",cycles);
            completed_frames=completed_frames+1;
            $display("Frame %0d pixels=%0d cycles=%0d fps=%f",completed_frames,received,cycles,125000000.0/cycles);
            if(completed_frames==target_frames) begin
                i=$fopen(result_file,"w");
                $fdisplay(i,"{\"cycles\":%0d,\"read_wait\":%0d,\"write_wait\":%0d,\"read_beats\":%0d,\"invalid_pixels\":%0d,\"pixels_checked\":%0d,\"frames_checked\":%0d,\"latency\":%0d,\"gap\":%0d,\"display_beats\":%0d,\"capture_beats\":%0d,\"background_period\":%0d}",cycles,rd_wait,wr_wait,read_beats,invalid,received*completed_frames,completed_frames,latency,gap,display_beats,capture_beats,period);$fclose(i);
                $display("PASS native complete frames=%0d",completed_frames);$finish;
            end else begin
                received=0;
                for(i=0;i<2073600;i=i+1)seen[i]=0;
                $readmemh(golden2_file,golden);
            end
        end
        if(wall_cycles>12000000) $fatal(1,"Timeout fs=%0d ls=%0d ws=%0d",dut.fs,dut.ls,dut.ws);
    end
    always @(negedge clk) if(rst_n) begin
        random_state={random_state[30:0],random_state[31]^random_state[21]^random_state[1]^random_state[0]};
        src_gnt=src_req;arready=(rremain==0 && random_state[10:9]!=0);
        rvalid=0;rlast=0;
        if(rdelay>0) rdelay=rdelay-1;
        else if(rremain>0 && (gap==0 || random_state%gap!=0) && (wremain==0 || random_state[12])) begin
            rvalid=1;rlast=(rremain==1);rid=read_id;
            rrow=1079-((raddress&20'hfffff)/960);rx=((raddress&20'hfffff)%960)*2;
            for(i=0;i<16;i=i+1) rdata[i*16+:16]=read_id==1?source_pixel(rx+i,rrow):16'd0;
        end
        awready=(wremain==0 && random_state[3:2]!=0);
        wpull=0;wlast=0;
        if(wdelay>0) wdelay=wdelay-1;
        else if(wremain>0 && !rvalid && random_state[6:5]!=0) begin wpull=1;wlast=(wremain==1);end
    end
endmodule
