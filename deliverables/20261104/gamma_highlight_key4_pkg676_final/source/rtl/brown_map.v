`timescale 1ns/1ps
// Fully pipelined Brown4 inverse map. Initiation interval = 1 clock.
// Host compiles K^-1*A into Q28 linear and Q20 offset coefficients. The
// Brown polynomial and pixel projection are evaluated in FPGA, not on the PC.
// Datapath registers are deliberately separated across multiply/add boundaries.
module brown_map(
    input wire clk, rst_n,
    input wire [511:0] cfg,
    input wire in_valid,
    input wire [10:0] u,v,
    output reg out_valid, out_inside,
    output reg [26:0] sx,sy
);
    wire signed [31:0] n11=cfg[0*32+:32],n12=cfg[1*32+:32],n13=cfg[2*32+:32];
    wire signed [31:0] n21=cfg[3*32+:32],n22=cfg[4*32+:32],n23=cfg[5*32+:32];
    wire signed [31:0] fx=cfg[6*32+:32],fy=cfg[7*32+:32];
    wire signed [31:0] cx=cfg[8*32+:32],cy=cfg[9*32+:32];
    wire signed [23:0] k1=cfg[10*32+:24],k2=cfg[11*32+:24];
    wire signed [23:0] p1=cfg[12*32+:24],p2=cfg[13*32+:24];
    wire signed [25:0] k1_q20=$signed({{2{k1[23]}},k1})>>>2;

    reg [27:0] valid;
    reg [27:2] norm_valid;
    reg signed [43:0] nx0,nx1,ny0,ny1;
    reg signed [44:0] nx_sum,ny_sum;
    wire signed [44:0] nx_wide=(nx_sum>>>8)+$signed(n13);
    wire signed [44:0] ny_wide=(ny_sum>>>8)+$signed(n23);
    wire norm_ok=nx_wide>=-45'sd1572864 && nx_wide<=45'sd1572864 &&
                 ny_wide>=-45'sd1572864 && ny_wide<=45'sd1572864;
    wire projective_enable=cfg[14*32+3];
    wire signed [15:0] projective_g0=cfg[14*32+16+:16];
    wire signed [15:0] projective_g1=cfg[15*32+16+:16];
    wire projective_ok;
    wire signed [23:0] projective_x,projective_y;
    projective_divide u_projective(
        .clk(clk),.rst_n(rst_n),.in_valid(valid[1]),
        .x(nx_wide[23:0]),.y(ny_wide[23:0]),
        .g0(projective_g0),.g1(projective_g1),
        .out_valid(),.out_ok(projective_ok),
        .out_x(projective_x),.out_y(projective_y));
    reg signed [23:0] bypass_x[0:10],bypass_y[0:10];
    reg [14:0] projective_ok_delay;
    reg signed [23:0] xp[2:8],yp[2:8];
    reg signed [47:0] xx3,yy3,xy3;
    reg signed [25:0] xx4,yy4,xy4;
    reg signed [25:0] r2[4:6];
    reg signed [49:0] k2r5,pxy5,pyx5;
    reg signed [27:0] tx5,ty5;
    reg signed [25:0] t6,pxy6,pyx6;
    reg signed [51:0] tanx6,tany6,tr7;
    reg signed [27:0] tanx[7:10],tany[7:10];
    reg signed [25:0] pxy[7:9],pyx[7:9];
    reg signed [27:0] radial8;
    reg signed [51:0] xr9,yr9;
    reg signed [31:0] xd10,yd10,xd11,yd11;
    wire signed [63:0] projected_x,projected_y;
    reg signed [47:0] sx13,sy13;
    mul32_pipe u_project_x(clk,fx,xd11,projected_x);
    mul32_pipe u_project_y(clk,fy,yd11,projected_y);
    integer i;

    // Only valid/ownership state requires reset. Leaving arithmetic registers
    // unreset enables native DSP pipeline mapping and avoids reset fanout.
    always @(posedge clk) begin
        nx0<=n11*$signed({1'b0,u}); nx1<=n12*$signed({1'b0,v});
        ny0<=n21*$signed({1'b0,u}); ny1<=n22*$signed({1'b0,v});
        nx_sum<=$signed({nx0[43],nx0})+$signed({nx1[43],nx1});
        ny_sum<=$signed({ny0[43],ny0})+$signed({ny1[43],ny1});
        bypass_x[0]<=nx_wide[23:0];bypass_y[0]<=ny_wide[23:0];
        for(i=1;i<=10;i=i+1) begin
            bypass_x[i]<=bypass_x[i-1];bypass_y[i]<=bypass_y[i-1];
        end
        xp[2]<=norm_valid[12] && (!projective_enable || projective_ok) ?
               (projective_enable?projective_x:bypass_x[10]) : 24'sd0;
        yp[2]<=norm_valid[12] && (!projective_enable || projective_ok) ?
               (projective_enable?projective_y:bypass_y[10]) : 24'sd0;
        for(i=3;i<=8;i=i+1) begin xp[i]<=xp[i-1];yp[i]<=yp[i-1];end
        xx3<=xp[2]*xp[2]; yy3<=yp[2]*yp[2]; xy3<=xp[2]*yp[2];
        xx4<=xx3>>>20; yy4<=yy3>>>20; xy4<=xy3>>>20;
        r2[4]<=(xx3>>>20)+(yy3>>>20);
        r2[5]<=r2[4];r2[6]<=r2[5];
        k2r5<=k2*r2[4];
        tx5<=$signed(r2[4])+($signed(xx4)<<<1);
        ty5<=$signed(r2[4])+($signed(yy4)<<<1);
        pxy5<=p1*xy4;pyx5<=p2*xy4;
        t6<=(k2r5>>>22)+k1_q20;
        tanx6<=p2*tx5;tany6<=p1*ty5;
        pxy6<=pxy5>>>22;pyx6<=pyx5>>>22;
        tr7<=t6*r2[6];
        tanx[7]<=tanx6>>>22;tany[7]<=tany6>>>22;
        pxy[7]<=pxy6;pyx[7]<=pyx6;
        radial8<=28'sd1048576+(tr7>>>20);
        for(i=8;i<=10;i=i+1) begin tanx[i]<=tanx[i-1];tany[i]<=tany[i-1];end
        for(i=8;i<=9;i=i+1) begin pxy[i]<=pxy[i-1];pyx[i]<=pyx[i-1];end
        xr9<=xp[8]*radial8;yr9<=yp[8]*radial8;
        xd10<=(xr9>>>20)+($signed(pxy[9])<<<1);
        yd10<=(yr9>>>20)+($signed(pyx[9])<<<1);
        xd11<=xd10+$signed(tanx[10]);yd11<=yd10+$signed(tany[10]);
        sx13<=(projected_x>>>20)+$signed(cx);sy13<=(projected_y>>>20)+$signed(cy);
        sx<=sx13[26:0];sy<=sy13[26:0];
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            valid<=0;norm_valid<=0;projective_ok_delay<=0;
            out_valid<=0;out_inside<=0;
        end
        else begin
            valid<={valid[26:0],in_valid};out_valid<=valid[27];
            norm_valid[2]<=norm_ok;
            for(i=3;i<=27;i=i+1) norm_valid[i]<=norm_valid[i-1];
            projective_ok_delay<={projective_ok_delay[13:0],projective_ok};
            out_inside<=norm_valid[27] && (!projective_enable || projective_ok_delay[14]) &&
                         sx13>=0 && sx13<=48'sd125763584 &&
                         sy13>=0 && sy13<=48'sd70713344;
        end
    end
endmodule
