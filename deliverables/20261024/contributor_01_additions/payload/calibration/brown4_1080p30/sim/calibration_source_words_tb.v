`timescale 1ns/1ps
module calibration_source_words_tb;
    reg [255:0] words[0:129599];
    reg [4:0] r,b;reg [5:0] g;
    reg [15:0] expected;
    integer pattern,n,lane,x,y,checked=0;
    initial begin
        for(pattern=0;pattern<2;pattern=pattern+1)begin
            if(pattern==0)$readmemh("vectors/source_words_0.hex",words);
            else $readmemh("vectors/source_words_1.hex",words);
            for(n=0;n<129600;n=n+1)begin
                y=1079-n/120;
                for(lane=0;lane<16;lane=lane+1)begin
                    x=(n%120)*16+lane;
                    if(pattern==0)begin
                        r=((x/64)+(y/128))&31;g=((x/40)+(y/80))&63;b=((x/80)+(y/64))&31;
                    end else begin
                        r=(x*13+y*7)&31;g=(x*29+y*11)&63;b=(x*3+y*23)&31;
                    end
                    expected={r,g,b};
                    if(words[n][lane*16+:16]!==expected)$fatal(1,"Source packing mismatch pattern=%0d n=%0d lane=%0d",pattern,n,lane);
                    checked=checked+1;
                end
            end
        end
        $display("SOURCE_WORDS PASS pixels=%0d row_flip_and_packing=1 matches_original_procedural_model=1",checked);
        $finish;
    end
endmodule
