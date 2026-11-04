`timescale 1ns/1ps
// Control-rate BNO085 pose-to-homography coefficient generator.
// The reference pose is captured in FPGA. Coefficients publish as one group.
// Quaternion identity and epoch are validated before use; invalid generations
// invalidate the map. Base calibration changes restart calculation, and map_cfg
// changes atomically only at the S_PUBLISH transaction boundary.
module imu_projective_map(
    input wire clk,rst_n,
    input wire enable,capture_toggle,
    input wire [383:0] imu_snapshot,
    input wire [511:0] base_cfg,
    input wire [15:0] base_sequence,
    output reg [511:0] map_cfg,
    output wire busy,
    output reg reference_valid,map_valid,
    output reg [7:0] capture_generation,
    output reg config_update
);
    localparam S_IDLE=0,S_ROT=1,S_ROT_SUM=13,S_MATRIX=2,S_MATRIX2=3,S_NUM=4,S_NUM_W1=5,
               S_NUM_W2=6,S_NUM_W3=7,S_NUM_W4=8,S_ACCUM=9,
               S_PREP=10,S_DIV=11,S_PUBLISH=12,S_NUM_W5=14;
    reg [3:0] state;
    reg capture_seen,capture_pending;
    reg [23:0] last_pose_count;
    reg [18:0] last_imu_epoch,epoch_latched;
    reg [511:0] base_latched;
    reg [15:0] last_base_sequence;
    reg base_sync_pending;
    reg signed [15:0] reference_q[0:3];
    reg signed [15:0] qx_latched,qy_latched,qz_latched,qw_latched;
    reg signed [15:0] rx_latched,ry_latched,rz_latched,rw_latched;
    reg delta_identity;
    wire [23:0] pose_count=imu_snapshot[375:352];
    wire [18:0] imu_epoch={imu_snapshot[383:381],imu_snapshot[223:208]};
    wire imu_epoch_changed=imu_epoch!=last_imu_epoch;
    wire pose_valid=(imu_snapshot[31:0]==32'h424e4f01) && imu_snapshot[377];
    wire pose_changed=pose_valid && pose_count!=last_pose_count;
    wire capture_event=(capture_pending || capture_toggle!=capture_seen) && pose_valid;
    wire base_changed=base_sequence!=last_base_sequence;
    wire start_update=enable && !base_sync_pending && state==S_IDLE && pose_valid && !imu_epoch_changed &&
        (capture_event || (reference_valid && (pose_changed || base_changed)));
    assign busy=(state!=S_IDLE) || start_update || base_sync_pending || base_changed ||
                ((!enable || imu_epoch_changed) && map_valid);

    wire signed [15:0] qx=imu_snapshot[271:256];
    wire signed [15:0] qy=imu_snapshot[287:272];
    wire signed [15:0] qz=imu_snapshot[303:288];
    wire signed [15:0] qw=imu_snapshot[319:304];
    wire signed [31:0] dq_x_pair0=$signed(qw_latched)*$signed(rx_latched)-
                                   $signed(qx_latched)*$signed(rw_latched);
    wire signed [31:0] dq_x_pair1=$signed(qz_latched)*$signed(ry_latched)-
                                   $signed(qy_latched)*$signed(rz_latched);
    wire signed [31:0] dq_y_pair0=$signed(qw_latched)*$signed(ry_latched)-
                                   $signed(qx_latched)*$signed(rz_latched);
    wire signed [31:0] dq_y_pair1=$signed(qz_latched)*$signed(rx_latched)-
                                   $signed(qy_latched)*$signed(rw_latched);
    wire signed [31:0] dq_z_pair0=$signed(qw_latched)*$signed(rz_latched)-
                                   $signed(qx_latched)*$signed(ry_latched);
    wire signed [31:0] dq_z_pair1=$signed(qy_latched)*$signed(rx_latched)-
                                   $signed(qz_latched)*$signed(rw_latched);
    wire signed [31:0] dq_w_pair0=$signed(qw_latched)*$signed(rw_latched)+
                                   $signed(qx_latched)*$signed(rx_latched);
    wire signed [31:0] dq_w_pair1=$signed(qy_latched)*$signed(ry_latched)+
                                   $signed(qz_latched)*$signed(rz_latched);
    reg signed [31:0] dq_x_pair0_q,dq_x_pair1_q,dq_y_pair0_q,dq_y_pair1_q;
    reg signed [31:0] dq_z_pair0_q,dq_z_pair1_q,dq_w_pair0_q,dq_w_pair1_q;
    reg signed [15:0] dx,dy,dz,dw;
    wire signed [31:0] xx=$signed(dx)*$signed(dx),yy=$signed(dy)*$signed(dy);
    wire signed [31:0] zz=$signed(dz)*$signed(dz),ww=$signed(dw)*$signed(dw);
    wire signed [31:0] xy=$signed(dx)*$signed(dy),xz=$signed(dx)*$signed(dz);
    wire signed [31:0] yz=$signed(dy)*$signed(dz),xw=$signed(dx)*$signed(dw);
    wire signed [31:0] yw=$signed(dy)*$signed(dw),zw=$signed(dz)*$signed(dw);
    reg signed [31:0] xx_q,yy_q,zz_q,xy_q,xz_q,yz_q,xw_q,yw_q,zw_q;
    wire signed [31:0] one_q28=32'sd268435456;
    wire signed [31:0] s00=one_q28-((yy_q+zz_q)<<<1);
    wire signed [31:0] s01=(xy_q-zw_q)<<<1;
    wire signed [31:0] s02=(xz_q+yw_q)<<<1;
    wire signed [31:0] s10=(xy_q+zw_q)<<<1;
    wire signed [31:0] s11=one_q28-((xx_q+zz_q)<<<1);
    wire signed [31:0] s12=(yz_q-xw_q)<<<1;
    wire signed [31:0] s20=(xz_q-yw_q)<<<1;
    wire signed [31:0] s21=(yz_q+xw_q)<<<1;
    wire signed [31:0] s22=one_q28-((xx_q+yy_q)<<<1);

    // The validated camera_from_sensor mount is a signed axis permutation.
    reg signed [31:0] r00,r01,r02,r10,r11,r12,r20,r21,r22;

    wire signed [31:0] b0=base_latched[0*32+:32],b1=base_latched[1*32+:32];
    wire signed [31:0] b2=base_latched[2*32+:32],b3=base_latched[3*32+:32];
    wire signed [31:0] b4=base_latched[4*32+:32],b5=base_latched[5*32+:32];
    reg signed [63:0] m00,m01,m03,m04,m02,m05,m10,m11,m13,m14,m12,m15;
    reg [3:0] mul_issue_index;
    reg [4:0] mul_valid_pipe;
    reg [19:0] mul_tag_pipe;
    reg signed [31:0] mul_shared_a,mul_shared_b;
    wire signed [63:0] mul_shared_product;
    // These 12 products are only needed when the IMU pose or calibration
    // changes. Issue them on consecutive clocks through one II=1 multiplier;
    // this control path does not feed the per-pixel video pipeline.
    always @* begin
        mul_shared_a=0;
        mul_shared_b=0;
        case(mul_issue_index)
            0: begin mul_shared_a=r00;mul_shared_b=b0;end
            1: begin mul_shared_a=r00;mul_shared_b=b1;end
            2: begin mul_shared_a=r01;mul_shared_b=b3;end
            3: begin mul_shared_a=r01;mul_shared_b=b4;end
            4: begin mul_shared_a=r00;mul_shared_b=b2;end
            5: begin mul_shared_a=r01;mul_shared_b=b5;end
            6: begin mul_shared_a=r10;mul_shared_b=b0;end
            7: begin mul_shared_a=r10;mul_shared_b=b1;end
            8: begin mul_shared_a=r11;mul_shared_b=b3;end
            9: begin mul_shared_a=r11;mul_shared_b=b4;end
            10: begin mul_shared_a=r10;mul_shared_b=b2;end
            11: begin mul_shared_a=r11;mul_shared_b=b5;end
            default: ;
        endcase
    end
    mul32_pipe #(.EXTRA_FINAL_PIPE(1)) u_matrix_mul(
        clk,mul_shared_a,mul_shared_b,mul_shared_product);
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            mul_valid_pipe<=0;mul_tag_pipe<=0;
            m00<=0;m01<=0;m03<=0;m04<=0;m02<=0;m05<=0;
            m10<=0;m11<=0;m13<=0;m14<=0;m12<=0;m15<=0;
        end else begin
            mul_valid_pipe<={mul_valid_pipe[3:0],state==S_NUM};
            mul_tag_pipe<={mul_tag_pipe[15:0],mul_issue_index};
            if(mul_valid_pipe[4]) begin
                case(mul_tag_pipe[19:16])
                    0: m00<=mul_shared_product;
                    1: m01<=mul_shared_product;
                    2: m03<=mul_shared_product;
                    3: m04<=mul_shared_product;
                    4: m02<=mul_shared_product;
                    5: m05<=mul_shared_product;
                    6: m10<=mul_shared_product;
                    7: m11<=mul_shared_product;
                    8: m13<=mul_shared_product;
                    9: m14<=mul_shared_product;
                    10: m12<=mul_shared_product;
                    11: m15<=mul_shared_product;
                    default: ;
                endcase
            end
        end
    end
    wire signed [63:0] n0=m00+m03,n1=m01+m04;
    wire signed [63:0] n2=m02+m05+($signed({{32{r02[31]}},r02})<<<20);
    wire signed [63:0] n3=m10+m13,n4=m11+m14;
    wire signed [63:0] n5=m12+m15+($signed({{32{r12[31]}},r12})<<<20);
    wire signed [63:0] n6=$signed({{32{r20[31]}},r20})<<<14;
    wire signed [63:0] n7=$signed({{32{r21[31]}},r21})<<<14;
    reg signed [63:0] numerator[0:7];
    reg signed [63:0] result[0:7];
    reg signed [31:0] denominator;
    reg [2:0] div_index;
    reg [6:0] div_bit;
    reg [63:0] dividend,quotient;
    reg [32:0] remainder;
    reg [31:0] divisor;
    reg quotient_negative,calculation_valid;
    wire [32:0] trial_remainder={remainder[31:0],dividend[63]};
    wire divide_subtract=trial_remainder>={1'b0,divisor};
    wire [63:0] quotient_next={quotient[62:0],divide_subtract};
    wire [63:0] numerator_magnitude=numerator[div_index][63]?
                                      -numerator[div_index]:numerator[div_index];
    wire [31:0] denominator_magnitude=denominator[31]?-denominator:denominator;
    wire [31:0] result_g0=result[6][15:0];
    wire [31:0] result_g1=result[7][15:0];
    wire coefficient_overflow=(result[0][63:32]!={32{result[0][31]}}) ||
        (result[1][63:32]!={32{result[1][31]}}) ||
        (result[2][63:32]!={32{result[2][31]}}) ||
        (result[3][63:32]!={32{result[3][31]}}) ||
        (result[4][63:32]!={32{result[4][31]}}) ||
        (result[5][63:32]!={32{result[5][31]}});
    integer i;

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=S_IDLE;reference_valid<=0;map_valid<=0;capture_seen<=0;capture_pending<=0;
            config_update<=0;
            capture_generation<=0;
            last_pose_count<=0;base_latched<=0;map_cfg<=0;
            last_base_sequence<=0;base_sync_pending<=1;
            last_imu_epoch<=0;epoch_latched<=0;
            mul_issue_index<=0;
            qx_latched<=0;qy_latched<=0;qz_latched<=0;qw_latched<=0;
            rx_latched<=0;ry_latched<=0;rz_latched<=0;rw_latched<=0;delta_identity<=0;
            dx<=0;dy<=0;dz<=0;dw<=0;
            dq_x_pair0_q<=0;dq_x_pair1_q<=0;dq_y_pair0_q<=0;dq_y_pair1_q<=0;
            dq_z_pair0_q<=0;dq_z_pair1_q<=0;dq_w_pair0_q<=0;dq_w_pair1_q<=0;
            xx_q<=0;yy_q<=0;zz_q<=0;xy_q<=0;xz_q<=0;yz_q<=0;
            xw_q<=0;yw_q<=0;zw_q<=0;
            r00<=0;r01<=0;r02<=0;r10<=0;r11<=0;r12<=0;r20<=0;r21<=0;r22<=0;
            denominator<=0;div_index<=0;div_bit<=0;dividend<=0;quotient<=0;
            remainder<=0;divisor<=0;quotient_negative<=0;calculation_valid<=0;
            for(i=0;i<4;i=i+1) reference_q[i]<=0;
            for(i=0;i<8;i=i+1) begin numerator[i]<=0;result[i]<=0;end
        end else begin
            config_update<=0;
            capture_seen<=capture_toggle;
            last_imu_epoch<=imu_epoch;
            if(imu_epoch_changed) begin
                reference_valid<=0;
                map_valid<=0;
                map_cfg<=base_cfg;
                config_update<=1;
                last_base_sequence<=base_sequence;
                base_sync_pending<=0;
            end
            if(!enable) capture_pending<=0;
            else if(start_update && capture_event) capture_pending<=0;
            else if(capture_toggle!=capture_seen) capture_pending<=1;
            if(pose_valid) last_pose_count<=pose_count;
            if(state==S_IDLE && base_sync_pending) begin
                map_cfg<=base_cfg;map_valid<=0;last_base_sequence<=base_sequence;
                base_sync_pending<=0;config_update<=1;
            end else if(state==S_IDLE && !enable) begin
                map_cfg<=base_cfg;
                if(base_changed || map_valid) config_update<=1;
                map_valid<=0;
                last_base_sequence<=base_sequence;
            end else if(state==S_IDLE && base_changed && !start_update) begin
                map_cfg<=base_cfg;map_valid<=0;last_base_sequence<=base_sequence;
                config_update<=1;
            end
            if(start_update) begin
                if(capture_event) begin
                    reference_q[0]<=qx;reference_q[1]<=qy;
                    reference_q[2]<=qz;reference_q[3]<=qw;
                    reference_valid<=1;
                    capture_generation<=capture_generation+1'b1;
                end
                base_latched<=base_cfg;last_base_sequence<=base_sequence;
                epoch_latched<=imu_epoch;
                qx_latched<=qx;qy_latched<=qy;qz_latched<=qz;qw_latched<=qw;
                rx_latched<=capture_event?qx:reference_q[0];
                ry_latched<=capture_event?qy:reference_q[1];
                rz_latched<=capture_event?qz:reference_q[2];
                rw_latched<=capture_event?qw:reference_q[3];
                delta_identity<=capture_event;
                state<=S_ROT;
            end
            case(state)
                S_ROT: begin
                    dq_x_pair0_q<=delta_identity?0:dq_x_pair0;
                    dq_x_pair1_q<=delta_identity?0:dq_x_pair1;
                    dq_y_pair0_q<=delta_identity?0:dq_y_pair0;
                    dq_y_pair1_q<=delta_identity?0:dq_y_pair1;
                    dq_z_pair0_q<=delta_identity?0:dq_z_pair0;
                    dq_z_pair1_q<=delta_identity?0:dq_z_pair1;
                    dq_w_pair0_q<=delta_identity?0:dq_w_pair0;
                    dq_w_pair1_q<=delta_identity?0:dq_w_pair1;
                    state<=S_ROT_SUM;
                end
                S_ROT_SUM: begin
                    if(delta_identity) begin dx<=0;dy<=0;dz<=0;dw<=16'sd16384;end
                    else begin
                        dx<=(dq_x_pair0_q+dq_x_pair1_q)>>>14;
                        dy<=(dq_y_pair0_q+dq_y_pair1_q)>>>14;
                        dz<=(dq_z_pair0_q+dq_z_pair1_q)>>>14;
                        dw<=(dq_w_pair0_q+dq_w_pair1_q)>>>14;
                    end
                    state<=S_MATRIX;
                end
                S_MATRIX: begin
                    xx_q<=xx;yy_q<=yy;zz_q<=zz;xy_q<=xy;xz_q<=xz;yz_q<=yz;
                    xw_q<=xw;yw_q<=yw;zw_q<=zw;
                    state<=S_MATRIX2;
                end
                S_MATRIX2: begin
                    r00<=s11;r01<=s12;r02<=-s10;
                    r10<=s21;r11<=s22;r12<=-s20;
                    r20<=-s01;r21<=-s02;r22<=s00;
                    mul_issue_index<=0;
                    state<=S_NUM;
                end
                S_NUM: begin
                    if(mul_issue_index==11) state<=S_NUM_W1;
                    else mul_issue_index<=mul_issue_index+1'b1;
                end
                S_NUM_W1: begin
                    state<=S_NUM_W2;
                end
                S_NUM_W2: begin
                    state<=S_NUM_W3;
                end
                S_NUM_W3: begin
                    state<=S_NUM_W4;
                end
                S_NUM_W4: begin
                    state<=S_NUM_W5;
                end
                S_NUM_W5: begin
                    state<=S_ACCUM;
                end
                S_ACCUM: begin
                    denominator<=r22;
                    numerator[0]<=n0;numerator[1]<=n1;numerator[2]<=n2;
                    numerator[3]<=n3;numerator[4]<=n4;numerator[5]<=n5;
                    numerator[6]<=n6;numerator[7]<=n7;
                    calculation_valid<=r22>=32'sd134217728;
                    div_index<=0;state<=S_PREP;
                end
                S_PREP: begin
                    dividend<=numerator_magnitude;quotient<=0;remainder<=0;
                    divisor<=denominator_magnitude;
                    quotient_negative<=numerator[div_index][63]^denominator[31];
                    div_bit<=63;state<=S_DIV;
                end
                S_DIV: begin
                    dividend<={dividend[62:0],1'b0};
                    if(divide_subtract) remainder<=trial_remainder-{1'b0,divisor};
                    else remainder<=trial_remainder;
                    quotient<=quotient_next;
                    if(div_bit==0) begin
                        result[div_index]<=quotient_negative?-quotient_next:quotient_next;
                        if(div_index==7) state<=S_PUBLISH;
                        else begin div_index<=div_index+1'b1;state<=S_PREP;end
                    end else div_bit<=div_bit-1'b1;
                end
                S_PUBLISH: begin
                    config_update<=1;
                    if(enable && reference_valid && epoch_latched==imu_epoch &&
                       calculation_valid && !coefficient_overflow &&
                       result[6][63:16]=={48{result[6][15]}} &&
                       result[7][63:16]=={48{result[7][15]}}) begin
                        map_cfg<=base_latched;
                        map_cfg[0*32+:32]<=result[0][31:0];
                        map_cfg[1*32+:32]<=result[1][31:0];
                        map_cfg[2*32+:32]<=result[2][31:0];
                        map_cfg[3*32+:32]<=result[3][31:0];
                        map_cfg[4*32+:32]<=result[4][31:0];
                        map_cfg[5*32+:32]<=result[5][31:0];
                        map_cfg[14*32+:32]<={result_g0[15:0],12'd0,1'b1,1'b0,1'b0,base_latched[14*32]};
                        map_cfg[15*32+:32]<={result_g1[15:0],base_latched[15*32+:16]};
                        map_valid<=1;
                    end else begin map_cfg<=base_cfg;map_valid<=0;end
                    state<=S_IDLE;
                end
                default: ;
            endcase
        end
    end
endmodule
