`timescale 1ns/1ps
module adaptive_gamma_curve_tb;
    reg [2:0] curve=0;
    reg [15:0] pixel=0;
    wire [15:0] got;
    integer c,p,r,g,b,er,eg,eb,err=0,checks=0;
    real exponent;
    reg [15:0] expected;
    adaptive_gamma_curve dut(.i_curve(curve),.i_pix(pixel),.o_pix(got));
    function integer lookup;
        input integer value;
        input real exp;
        real result;
        begin
            result=255.0*((value/255.0)**exp);
            lookup=$rtoi(result+0.5);
        end
    endfunction
    initial begin
        for(c=0;c<5;c=c+1) begin
            case(c) 0:exponent=0.6;1:exponent=0.8;2:exponent=1.0;
                    3:exponent=1.25;4:exponent=1.6;endcase
            curve=c;
            for(p=0;p<65536;p=p+1) begin
                pixel=p;
                r=(p>>11)&31;g=(p>>5)&63;b=p&31;
                er=lookup(r*8+r/4,exponent)/8;
                eg=lookup(g*4+g/16,exponent)/4;
                eb=lookup(b*8+b/4,exponent)/8;
                expected=(er<<11)|(eg<<5)|eb;
                #1;
                if(got!==expected) err=err+1;
                if(c==2 && got!==pixel) err=err+1;
                checks=checks+1;
            end
        end
        $display("EXHAUSTIVE_RGB565_CHECKS=%0d err=%0d",checks,err);
        if(err==0) $display("=== ALL TESTS PASSED (err=0) ===");
        else $display("FAIL err=%0d",err);
        $finish;
    end
endmodule
