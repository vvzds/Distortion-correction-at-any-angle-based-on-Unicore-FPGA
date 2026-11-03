`timescale 1ns/1ps
module brown_map_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,in_valid=0;
    reg [10:0] u=0,v=0;
    reg [511:0] cfg;
    reg [31:0] words[0:15];
    wire out_valid,out_inside;wire [26:0] sx,sy;
    brown_map dut(clk,rst_n,cfg,in_valid,u,v,out_valid,out_inside,sx,sy);
    integer inf,expected,n,a,b,c,d,e,j,count=0,sent=0;
    reg [1023:0] vectors,config_file;
    initial begin
        if(!$value$plusargs("VECTORS=%s",vectors)) $fatal(1,"VECTORS missing");
        if(!$value$plusargs("CONFIG=%s",config_file)) $fatal(1,"CONFIG missing");
        $readmemh(config_file,words);
        for(j=0;j<16;j=j+1) cfg[j*32+:32]=words[j];
        inf=$fopen(vectors,"r");expected=$fopen(vectors,"r");
        if(!inf || !expected) $fatal(1,"Cannot open vectors");
        repeat(5) @(negedge clk);rst_n=1;
        while(!$feof(inf)) begin
            @(negedge clk);
            n=$fscanf(inf,"%d %d %h %h %d\n",a,b,c,d,e);
            in_valid=(n==5);u=a;v=b;
            if(n==5) sent=sent+1;
            // Exercise pipeline bubbles without disturbing ordering.
            if(sent%97==0) begin @(negedge clk);in_valid=0;end
        end
        @(negedge clk);in_valid=0;
        repeat(40) @(negedge clk);
        if(count!=sent) $fatal(1,"Count mismatch %0d %0d",count,sent);
        $display("PASS brown_map pixels=%0d",count);$finish;
    end
    integer eu,ev,ex,ey,ei,en;
    always @(posedge clk) begin
        #1;
        if(rst_n && out_valid) begin
            en=$fscanf(expected,"%d %d %h %h %d\n",eu,ev,ex,ey,ei);
            if(en!=5) $fatal(1,"Unexpected output");
            if(out_inside!==ei[0] || (ei && (sx!==ex[26:0] || sy!==ey[26:0])))
                $fatal(1,"Map mismatch at %0d,%0d got %h,%h,%b expected %h,%h,%b",eu,ev,sx,sy,out_inside,ex,ey,ei[0]);
            count=count+1;
        end
    end
    initial begin #200000000;$fatal(1,"Timeout");end
endmodule
