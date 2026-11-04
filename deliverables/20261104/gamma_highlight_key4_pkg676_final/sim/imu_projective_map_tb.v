`timescale 1ns/1ps
module imu_projective_map_tb;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,enable=0,capture_toggle=0;
    reg [15:0] base_sequence=0;
    reg [383:0] imu_snapshot=0;
    reg [511:0] base_cfg=0;
    wire [511:0] map_cfg;
    wire busy,reference_valid,map_valid,config_update;wire [7:0] capture_generation;
    reg [31:0] config_words[0:15];
    imu_projective_map dut(.clk(clk),.rst_n(rst_n),.enable(enable),
        .capture_toggle(capture_toggle),.imu_snapshot(imu_snapshot),.base_cfg(base_cfg),
        .base_sequence(base_sequence),
        .map_cfg(map_cfg),.busy(busy),.reference_valid(reference_valid),.map_valid(map_valid),
        .capture_generation(capture_generation),.config_update(config_update));
    integer inf,n,action,count=0,i,result_out;
    integer qx_i,qy_i,qz_i,qw_i;
    reg [31:0] expected_words[0:7];
    reg [1023:0] vectors,config_file,result_file;
    reg [23:0] pose_count=0;
    initial begin
        if(!$value$plusargs("VECTORS=%s",vectors)) $fatal(1,"VECTORS missing");
        if(!$value$plusargs("CONFIG=%s",config_file)) $fatal(1,"CONFIG missing");
        if(!$value$plusargs("RESULT=%s",result_file)) $fatal(1,"RESULT missing");
        result_out=$fopen(result_file,"w");
        if(!result_out) $fatal(1,"Cannot open result file");
        $readmemh(config_file,config_words);
        for(i=0;i<16;i=i+1)base_cfg[i*32+:32]=config_words[i];
        inf=$fopen(vectors,"r");
        if(!inf) $fatal(1,"Cannot open vectors");
        repeat(5) @(negedge clk);rst_n=1;enable=1;
        while(!$feof(inf)) begin
            @(negedge clk);
            n=$fscanf(inf,"%d %d %d %d %d %h %h %h %h %h %h %h %h\n",
                      action,qx_i,qy_i,qz_i,qw_i,
                      expected_words[0],expected_words[1],expected_words[2],
                      expected_words[3],expected_words[4],expected_words[5],
                      expected_words[6],expected_words[7]);
            if(n==13) begin
                pose_count=pose_count+1'b1;
                imu_snapshot=0;
                imu_snapshot[31:0]=32'h424e4f01;
                imu_snapshot[375:352]=pose_count;
                imu_snapshot[377]=1'b1;
                imu_snapshot[319:304]=qw_i[15:0];
                imu_snapshot[303:288]=qz_i[15:0];
                imu_snapshot[287:272]=qy_i[15:0];
                imu_snapshot[271:256]=qx_i[15:0];
                if(action)capture_toggle=~capture_toggle;
                wait(busy==1);wait(busy==0);@(negedge clk);
                if(!config_update)
                    $fatal(1,"Configuration update pulse missing at case %0d",count);
                if(!reference_valid || !map_valid || !map_cfg[14*32+3])
                    $fatal(1,"Auto projective mode/reference missing at case %0d",count);
                $fdisplay(result_out,"%0d %h %h %h %h %h %h %h %h",count,
                    map_cfg[0*32+:32],map_cfg[1*32+:32],map_cfg[2*32+:32],
                    map_cfg[3*32+:32],map_cfg[4*32+:32],map_cfg[5*32+:32],
                    map_cfg[14*32+31:14*32+16],map_cfg[15*32+31:15*32+16]);
                for(i=0;i<6;i=i+1)
                    if($signed(map_cfg[i*32+:32])-$signed(expected_words[i])>2 ||
                       $signed(expected_words[i])-$signed(map_cfg[i*32+:32])>2)
                        $fatal(1,"Affine coefficient %0d mismatch case %0d got %h expected %h",
                               i,count,map_cfg[i*32+:32],expected_words[i]);
                if($signed(map_cfg[14*32+31:14*32+16])-$signed(expected_words[6][15:0])>1 ||
                   $signed(expected_words[6][15:0])-$signed(map_cfg[14*32+31:14*32+16])>1 ||
                   $signed(map_cfg[15*32+31:15*32+16])-$signed(expected_words[7][15:0])>1 ||
                   $signed(expected_words[7][15:0])-$signed(map_cfg[15*32+31:15*32+16])>1)
                    $fatal(1,"Projective slope mismatch case %0d",count);
                count=count+1;
            end
        end
        if(count!=4)$fatal(1,"Unexpected vector count %0d",count);
        $fclose(result_out);
        if(capture_generation!=2)$fatal(1,"Expected two reference captures, got %0d",capture_generation);
        imu_snapshot[383:381]=1;@(posedge clk);#1;
        if(!config_update)$fatal(1,"Configuration update pulse missing on IMU epoch change");
        repeat(2) @(negedge clk);
        if(reference_valid || map_valid || map_cfg!==base_cfg)
            $fatal(1,"IMU epoch change did not invalidate reference/restore base config");
        enable=0;repeat(2) @(negedge clk);
        if(map_cfg[14*32+3] || map_cfg!==base_cfg)
            $fatal(1,"Manual configuration was not restored on disable");
        @(negedge clk);base_cfg[8*32+:32]=base_cfg[8*32+:32]+1;base_sequence=1;
        wait(busy);@(posedge clk);#1;
        if(!config_update || map_cfg!==base_cfg)
            $fatal(1,"Base configuration sequence did not restore the updated map");
        @(negedge clk);
        if(busy)$fatal(1,"Base configuration update did not settle");
        $display("PASS imu_projective_map poses=%0d",count);$finish;
    end
    initial begin #2000000;$fatal(1,"Timeout state=%0d",dut.state);end
endmodule
