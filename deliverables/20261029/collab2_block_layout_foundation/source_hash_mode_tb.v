`timescale 1ns/1ps
module source_hash_mode_tb;
    reg affine_enable=0;
    reg signed [31:0] a11_q16=0,a21_q16=0;
    wire vertical_hash;
    integer checks=0;
    source_hash_mode dut(affine_enable,a11_q16,a21_q16,vertical_hash);
    task check;
        input integer en,a11,a21,expected;
        begin
            affine_enable=en;a11_q16=a11;a21_q16=a21;#1;
            if(vertical_hash!==expected)begin
                $display("FAIL en=%0d a11=%0d a21=%0d got=%0d expected=%0d",
                         en,a11,a21,vertical_hash,expected);$fatal;
            end
            checks=checks+1;
        end
    endtask
    initial begin
        check(0,0,65536,0);
        check(1,65536,0,0);
        check(1,11380,64540,0);  // 80 degrees
        check(1,5712,65287,1);   // 85 degrees
        check(1,0,65536,1);      // 90 degrees
        check(1,-46341,46341,0); // 135 degrees
        check(1,-65536,0,0);     // 180 degrees
        check(1,0,-65536,1);     // 270 degrees
        check(1,63303,-16962,0); // -15 degrees
        check(1,8192,65536,0);   // strict threshold
        check(1,8191,65536,1);
        $display("PASS source_hash_mode cases=%0d",checks);
        $finish;
    end
endmodule
