`timescale 1ns/1ps
module source_block_quad_tb;
    reg [10:0] x=0,y_storage=0;
    wire [14:0] b00,b01,b10,b11;
    wire [2:0] beat_top,beat_bottom;
    wire [3:0] lane_left,lane_right;
    wire valid;
    integer row,col,xr,yb,n=0;
    source_block_quad dut(x,y_storage,b00,b01,b10,b11,
                          beat_top,beat_bottom,lane_left,lane_right,valid);
    initial begin
        for(row=0;row<1080;row=row+1)
            for(col=0;col<1920;col=col+1)begin
                x=col;y_storage=row;
                xr=col==1919?col:col+1;
                yb=row==0?row:row-1;
                #1;
                if(!valid || b00!==((row/8)*120+col/16) ||
                   b01!==((row/8)*120+xr/16) ||
                   b10!==((yb/8)*120+col/16) ||
                   b11!==((yb/8)*120+xr/16) ||
                   beat_top!==(row%8) || beat_bottom!==(yb%8) ||
                   lane_left!==(col%16) || lane_right!==(xr%16))begin
                    $display("FAIL x=%0d y=%0d b00=%0d b01=%0d b10=%0d b11=%0d",
                             col,row,b00,b01,b10,b11);$fatal;
                end
                n=n+1;
            end
        x=1920;y_storage=0;#1;if(valid)$fatal;
        x=0;y_storage=1080;#1;if(valid)$fatal;
        $display("PASS source_block_quad exhaustive pixels=%0d",n);
        $finish;
    end
endmodule
