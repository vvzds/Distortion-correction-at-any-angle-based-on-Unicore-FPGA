`timescale 1ns/1ps
module feature_config_gate_tb;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0;
    reg [4:0] key_n=5'b11111;
    reg affine_pc_update=0,affine_pc_enable=0;
    reg quality_pc_update=0,osd_pc_update=0,osd_pc_visible=0;
    reg [511:0] correction_config=0;
    wire brown_enable,affine_enable,affine_capture_toggle,stabilization_lock_request;
    wire gamma_enable,osd_visible;
    wire [1:0] quality_profile;
    wire [511:0] feature_config;
    integer i;

    feature_key_control #(.DEBOUNCE_CYCLES(4)) u_keys(
        .clk(clk),.rst_n(rst_n),.key_n(key_n),
        .affine_pc_update(affine_pc_update),.affine_pc_enable(affine_pc_enable),
        .quality_pc_update(quality_pc_update),.osd_pc_update(osd_pc_update),
        .osd_pc_visible(osd_pc_visible),.brown_enable(brown_enable),
        .affine_enable(affine_enable),.affine_capture_toggle(affine_capture_toggle),
        .stabilization_lock_request(stabilization_lock_request),
        .gamma_enable(gamma_enable),.quality_profile(quality_profile),
        .osd_visible(osd_visible));

    feature_config_gate u_gate(
        .correction_config(correction_config),.brown_enable(brown_enable),
        .gamma_enable(gamma_enable),.feature_config(feature_config));

    task settle;
        begin repeat(12) @(negedge clk); end
    endtask
    task tap_key;
        input integer key_index;
        begin
            @(negedge clk);key_n[key_index]=1'b0;
            repeat(12) @(negedge clk);
            key_n[key_index]=1'b1;
            settle();
        end
    endtask
    task check_matrix;
        input [511:0] expected;
        input [8*64-1:0] label_text;
        begin
            #1;
            if(feature_config!==expected) $fatal(1,"%0s",label_text);
        end
    endtask

    reg [511:0] expected;
    initial begin
        for(i=0;i<16;i=i+1) correction_config[i*32+:32]=32'h31000000+i;
        correction_config[14*32]=1'b1;
        correction_config[14*32+3]=1'b1;
        correction_config[15*32+17]=1'b1;
        correction_config[2*32+:32]=32'hfff6a39c;
        correction_config[5*32+:32]=32'h00014567;
        repeat(3) @(negedge clk);rst_n=1;settle();
        check_matrix(correction_config,"Host matrix must pass while KEY1 is off");

        tap_key(1);
        if(!affine_enable || !affine_capture_toggle) $fatal(1,"KEY1 did not enable IMU mapping");
        check_matrix(correction_config,"KEY1 on changed the host matrix path");
        correction_config[2*32+:32]=32'hfff12345;
        check_matrix(correction_config,"New host matrix was lost while KEY1 was on");
        tap_key(1);
        if(affine_enable) $fatal(1,"KEY1 did not disable IMU mapping");
        check_matrix(correction_config,"KEY1 off replaced the current host matrix");

        expected=correction_config;
        tap_key(0);
        expected[10*32+:128]=0;
        check_matrix(expected,"KEY0 must gate Brown terms only");
        tap_key(2);
        expected[14*32]=1'b0;
        check_matrix(expected,"KEY2 must gate Gamma without changing geometry");
        if(expected[14*32+3]!==1'b1 || expected[15*32+17]!==1'b1)
            $fatal(1,"Test vector lost projective/smoothing flags");

        $display("PASS host affine pass-through, independent IMU/Brown/Gamma key gates");
        $finish;
    end
    initial begin #100000;$fatal(1,"Timeout");end
endmodule
