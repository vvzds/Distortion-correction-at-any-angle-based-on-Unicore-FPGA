`timescale 1ns/1ps
module adaptive_gamma_tb;
    reg clk=0;
    always #4 clk=~clk;
    reg rst_n=0,en=0,v=0,sop=0,eop=0,sof=0,eof=0;
    reg [15:0] p=0;
    wire ov;
    wire [15:0] op;
    reg [63:0] vec;
    integer fd,rc,n=0,err=0;
    adaptive_gamma #(.WIDTH(8),.HEIGHT(4)) dut(
        .clk(clk),.rst_n(rst_n),.i_enable(en),.i_pix_vld(v),.i_pix(p),
        .i_sop(sop),.i_eop(eop),.i_sof(sof),.i_eof(eof),
        .o_pix_vld(ov),.o_pix(op));
    initial begin
        fd=$fopen("vectors.mem","r");
        if(fd==0) begin $display("FAIL missing vectors"); $finish; end
        while(!$feof(fd)) begin
            rc=$fscanf(fd,"%h\n",vec);
            if(rc==1) begin
                @(negedge clk);
                p=vec[15:0];v=vec[16];sop=vec[17];eop=vec[18];
                sof=vec[19];eof=vec[20];en=vec[21];rst_n=vec[22];
                @(posedge clk);#1;
                if(ov!==vec[39] || (vec[39] && op!==vec[38:23])) begin
                    if(err<10) $display("FAIL vector=%0d got=%h expected=%h",n,op,vec[38:23]);
                    err=err+1;
                end
                n=n+1;
            end
        end
        $fclose(fd);
        if(n<1000) err=err+1;
        $display("VECTORS=%0d err=%0d",n,err);
        if(err==0) $display("=== ALL TESTS PASSED (err=0) ===");
        else $display("FAIL err=%0d",err);
        $finish;
    end
endmodule
