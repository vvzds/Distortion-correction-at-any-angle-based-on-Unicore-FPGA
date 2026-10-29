`timescale 1ns/1ps
module source_block_addr_tb;
    reg [10:0] x=0,y_storage=0;
    wire [19:0] block_word_addr,pixel_word_addr;
    wire [2:0] beat_in_block;
    wire [3:0] pixel_in_beat;
    wire valid;
    integer row,col,expected_block,expected_pixel,checks=0;
    source_block_addr dut(x,y_storage,block_word_addr,pixel_word_addr,
                          beat_in_block,pixel_in_beat,valid);
    initial begin
        for(row=0;row<1080;row=row+1)
            for(col=0;col<1920;col=col+1)begin
                x=col;y_storage=row;#1;
                expected_block=((row/8)*120+(col/16))*64;
                expected_pixel=expected_block+(row%8)*8+(col%16)/2;
                if(!valid || block_word_addr!==expected_block ||
                   pixel_word_addr!==expected_pixel ||
                   beat_in_block!==(row%8) ||
                   pixel_in_beat!==(col%16) ||
                   pixel_word_addr>=20'hfd200)begin
                    $display("FAIL x=%0d y=%0d block=%0d pixel=%0d",col,row,
                             block_word_addr,pixel_word_addr);$fatal;
                end
                checks=checks+1;
            end
        x=1920;y_storage=0;#1;if(valid)$fatal;
        x=0;y_storage=1080;#1;if(valid)$fatal;
        $display("PASS source_block_addr exhaustive pixels=%0d",checks);
        $finish;
    end
endmodule
