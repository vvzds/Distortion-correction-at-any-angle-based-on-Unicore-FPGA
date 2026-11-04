`timescale 1ns/1ps
module projective_divide_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,in_valid=0;
    reg signed [23:0] x=0,y=0;
    reg signed [15:0] g0=0,g1=0;
    wire out_valid,out_ok;
    wire signed [23:0] out_x,out_y;
    projective_divide dut(clk,rst_n,in_valid,x,y,g0,g1,
                          out_valid,out_ok,out_x,out_y);
    integer inf,expected,n,ix,iy,ig0,ig1,ex,ey,ev,count=0,sent=0;
    reg [1023:0] vectors;
    initial begin
        if(!$value$plusargs("VECTORS=%s",vectors)) $fatal(1,"VECTORS missing");
        inf=$fopen(vectors,"r");expected=$fopen(vectors,"r");
        if(!inf || !expected) $fatal(1,"Cannot open vectors");
        repeat(5) @(negedge clk);rst_n=1;
        while(!$feof(inf)) begin
            @(negedge clk);
            n=$fscanf(inf,"%h %h %h %h %h %h %d\n",ix,iy,ig0,ig1,ex,ey,ev);
            in_valid=(n==7);
            if(n==7) begin
                x=ix[23:0];y=iy[23:0];g0=ig0[15:0];g1=ig1[15:0];
                sent=sent+1;
            end
            if(n==7 && sent%31==0) begin
                @(negedge clk);in_valid=0;
            end
        end
        @(negedge clk);in_valid=0;
        repeat(16) @(negedge clk);
        if(count!=sent) $fatal(1,"Count mismatch %0d %0d",count,sent);
        $display("PASS projective_divide vectors=%0d",count);$finish;
    end
    integer ei,exi,eyi,eg0,eg1,eox,eoy,eok;
    always @(posedge clk) begin
        #1;
        if(rst_n && out_valid) begin
            ei=$fscanf(expected,"%h %h %h %h %h %h %d\n",exi,eyi,eg0,eg1,eox,eoy,eok);
            if(ei!=7) $fatal(1,"Unexpected output");
            if(out_ok!==eok[0])
                $fatal(1,"Validity mismatch at vector %0d got %b expected %d",count,out_ok,eok);
            if(eok && (out_x!==eox[23:0] || out_y!==eoy[23:0]))
                $fatal(1,"Map mismatch at vector %0d got %0d,%0d expected %0d,%0d",
                       count,out_x,out_y,$signed(eox[23:0]),$signed(eoy[23:0]));
            count=count+1;
        end
    end
    initial begin #20000000;$fatal(1,"Timeout");end
endmodule
