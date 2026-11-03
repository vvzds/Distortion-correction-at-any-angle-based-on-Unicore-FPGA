`timescale 1ns/1ps
module feature_key_control_tb;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0;
    reg [4:0] key_n=5'b11111;
    reg affine_pc_update=0,affine_pc_enable=0;
    reg quality_pc_update=0,osd_pc_update=0,osd_pc_visible=0;
    wire brown_enable,affine_enable,affine_capture_toggle,gamma_enable,osd_visible;
    wire [1:0] quality_profile;

    feature_key_control #(.DEBOUNCE_CYCLES(4)) dut(
        .clk(clk),.rst_n(rst_n),.key_n(key_n),
        .affine_pc_update(affine_pc_update),.affine_pc_enable(affine_pc_enable),
        .quality_pc_update(quality_pc_update),.osd_pc_update(osd_pc_update),
        .osd_pc_visible(osd_pc_visible),.brown_enable(brown_enable),
        .affine_enable(affine_enable),.affine_capture_toggle(affine_capture_toggle),
        .gamma_enable(gamma_enable),.quality_profile(quality_profile),
        .osd_visible(osd_visible));

    task settle;
        begin repeat(12) @(negedge clk); end
    endtask
    task tap_key;
        input integer key_index;
        begin
            @(negedge clk); key_n[key_index]=1'b0;
            settle();
            key_n[key_index]=1'b0;
            repeat(20) @(negedge clk);
            key_n[key_index]=1'b1;
            settle();
        end
    endtask
    task check;
        input condition;
        input [8*64-1:0] message;
        begin if(!condition) $fatal(1,"%0s",message); end
    endtask

    initial begin
        repeat(3) @(negedge clk); rst_n=1; settle();
        check(brown_enable && !affine_enable && gamma_enable &&
              quality_profile==0 && !osd_visible,"power-on defaults");

        // A long press is one event, and release does not change the mode.
        @(negedge clk); key_n[0]=0; repeat(30) @(negedge clk);
        check(!brown_enable,"KEY0 toggles Brown off");
        repeat(30) @(negedge clk);
        check(!brown_enable,"held KEY0 does not retrigger");
        key_n[0]=1; settle();
        tap_key(0); check(brown_enable,"KEY0 toggles Brown on");

        tap_key(1);
        check(affine_enable && affine_capture_toggle,"KEY1 enables and captures reference");
        tap_key(1);
        check(!affine_enable && affine_capture_toggle,"KEY1 disables without recapturing");
        affine_pc_enable=1;affine_pc_update=1;@(negedge clk);affine_pc_update=0;settle();
        check(affine_enable,"host affine enable synchronizes to KEY1 state");
        tap_key(1);check(!affine_enable,"KEY1 disables host-enabled affine mapping");
        affine_pc_enable=0;affine_pc_update=1;@(negedge clk);affine_pc_update=0;settle();
        tap_key(2); check(!gamma_enable,"KEY2 toggles Gamma off");

        tap_key(3); check(quality_profile==1,"KEY3 preset DN1");
        tap_key(3); check(quality_profile==2,"KEY3 preset DN1 plus SH1");
        tap_key(3); check(quality_profile==3,"KEY3 preset DN2 plus SH1");
        quality_pc_update=1; @(negedge clk); quality_pc_update=0; settle();
        check(quality_profile==0,"host quality command returns to host-selected levels");
        tap_key(3); check(quality_profile==1,"KEY3 restarts preset cycle");
        tap_key(3); tap_key(3); tap_key(3);
        check(quality_profile==0,"KEY3 cycles back to host-selected levels");

        tap_key(4); check(osd_visible,"KEY4 toggles OSD on");
        osd_pc_visible=1; osd_pc_update=1; @(negedge clk);
        osd_pc_update=0; settle();
        check(osd_visible,"host OSD-on state synchronizes with KEY4");
        osd_pc_visible=0; osd_pc_update=1; @(negedge clk);
        osd_pc_update=0; settle();
        check(!osd_visible,"host OSD-off state synchronizes with KEY4");
        tap_key(4); check(osd_visible,"KEY4 toggles after host command");

        $display("PASS key synchronization, debounce, toggles, profiles, host priority");
        $finish;
    end
endmodule
