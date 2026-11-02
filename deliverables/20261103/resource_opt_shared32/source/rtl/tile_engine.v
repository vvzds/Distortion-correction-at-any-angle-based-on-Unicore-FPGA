`timescale 1ns/1ps
// Three independent workers: map/bounds -> patch fetch -> render. Three
// coordinate contexts and two source/output buffers overlap these workers.
// Tile order is raster order, 64x32 (last row 64x24). Native write addresses
// scatter tile rows into their final frame positions; no stripe copy is needed.
module tile_engine(
    input wire clk,rst_n,frame_update,
    input wire [511:0] cfg,
    input wire config_pending,
    output reg busy,
    output reg src_req,
    input wire src_gnt,
    input wire [1:0] src_slot,
    output reg src_rel,
    output wire rd_req,
    output reg [23:0] rd_addr,
    output reg [6:0] rd_len,
    input wire rd_gnt,rd_valid,rd_last,
    input wire [255:0] rd_data,
    output reg slot_req,
    input wire slot_gnt,
    input wire [2:0] slot,
    output wire wr_req,
    output wire [23:0] wr_addr,
    output wire [31:0] wr_data,
    input wire wr_gnt,
    output wire commit,
    input wire published,
    output reg [31:0] frame_count,last_cycles,last_rd_wait,last_wr_wait,
    output reg [31:0] last_read_beats,last_invalid,
    output reg [31:0] overflow_tiles,
    output reg protocol_fault,
    output wire [1:0] gamma_mode,
    output reg [511:0] published_cfg
);
    localparam F_IDLE=0,F_ACQUIRE=1,F_RUN=2,F_COMMIT=3,F_PUBLISH=4,F_RELEASE=5;
    reg [2:0] fs;
    reg pending,have_src,have_dst;
    reg [1:0] source;
    reg [2:0] destination;
    reg [511:0] frame_cfg;
    reg [511:0] map_cfg_pipe;
    reg [31:0] cycles,read_wait,write_wait,read_beats,invalid_pixels;
    reg have_published;
    wire start_frame=fs==F_ACQUIRE && have_src && have_dst;
    reg all_written;
    assign commit=fs==F_COMMIT;

    function [1:0] next_context;
        input [1:0] a;
        begin next_context=(a==2)?0:a+1'b1;end
    endfunction
    function [23:0] row_word_address;
        input [10:0] row;
        reg [23:0] r;
        begin r={13'd0,row};row_word_address=(r<<10)-(r<<6);end
    endfunction

    localparam C_FREE=0,C_MAP=1,C_MAPPED=2,C_LOAD=3,C_READY=4,C_RENDER=5;
    reg [2:0] context_state[0:2];
    reg [4:0] tile_x[0:2];reg [5:0] tile_y[0:2],tile_h[0:2];
    reg [10:0] min_x[0:2],min_y[0:2],max_y[0:2];
    reg [4:0] patch_words[0:2];
    reg empty[0:2],patch_id[0:2];
    reg [39:0] coordinates[0:8191];

    // Mapping worker. Bounds include every valid mapped pixel and its right/
    // bottom neighbor; rounding of the bounds is solely for DDR alignment.
    reg map_active,map_done;
    reg [1:0] map_cursor,map_context;
    reg [4:0] next_tile_x;
    reg [5:0] next_tile_y;
    reg [11:0] map_issued,map_received,map_limit;
    reg [10:0] bound_min_x,bound_min_y,bound_max_x,bound_max_y;
    reg bound_any;
    wire map_in=fs==F_RUN && map_active && map_issued<map_limit;
    wire [10:0] map_u={tile_x[map_context],6'd0}+{5'd0,map_issued[5:0]};
    wire [10:0] map_v={tile_y[map_context],5'd0}+{6'd0,map_issued[10:6]};
    wire map_valid,map_inside;wire [26:0] sx,sy;
    always @(posedge clk) map_cfg_pipe<=frame_cfg;
    brown_map u_map(clk,rst_n,map_cfg_pipe,map_in,map_u,map_v,map_valid,map_inside,sx,sy);
    wire [10:0] neighbor_x=sx[26:16]==1919?11'd1919:sx[26:16]+1'b1;
    wire [10:0] neighbor_y=sy[26:16]==1079?11'd1079:sy[26:16]+1'b1;
    wire [10:0] next_min_x=(map_inside && sx[26:16]<bound_min_x)?sx[26:16]:bound_min_x;
    wire [10:0] next_min_y=(map_inside && sy[26:16]<bound_min_y)?sy[26:16]:bound_min_y;
    wire [10:0] next_max_x=(map_inside && neighbor_x>bound_max_x)?neighbor_x:bound_max_x;
    wire [10:0] next_max_y=(map_inside && neighbor_y>bound_max_y)?neighbor_y:bound_max_y;
    wire [7:0] bounds_words={1'b0,next_max_x[10:4]}-{1'b0,next_min_x[10:4]}+1'b1;
    wire [11:0] bounds_height={1'b0,next_max_y}-{1'b0,next_min_y[10:1],1'b0}+1'b1;
    wire bounds_empty=!(bound_any||map_inside);
    wire bounds_overflow=!bounds_empty && (bounds_words>16 || bounds_height>256);

    always @(posedge clk) if(map_active && map_valid)
        coordinates[{map_context,map_received[10:0]}]<=
            {1'b0,map_inside,sy[26:16],sx[26:16],sy[15:8],sx[15:8]};

    // Patch loader. Requests are one aligned source row at a time. The bridge
    // splits commands at DDR column boundaries and prioritizes HDMI reads.
    localparam L_IDLE=0,L_ADDRESS=1,L_REQUEST=2,L_RETURN=3;
    reg [1:0] ls,load_cursor,load_context;
    reg load_buffer,next_load_buffer;
    reg [1:0] patch_busy;
    reg [8:0] load_row;
    reg [4:0] load_beat;
    assign rd_req=fs==F_RUN && ls==L_REQUEST;
    wire cache_load=ls==L_RETURN && rd_valid;

    // Render pipeline: synchronous coordinate RAM -> local address -> parity
    // RAM -> pixel selection -> bilinear -> adaptive gamma -> output tile RAM.
    reg render_active;
    reg [1:0] render_cursor,render_context;
    reg render_buffer,next_render_buffer;
    reg [11:0] render_issued,render_received,render_limit;
    reg [39:0] coordinate;
    wire render_issue=render_active && render_issued<render_limit;
    reg coordinate_valid,decode_valid;
    reg [7:0] x0,y0,x1,y1,wx_dec,wy_dec;
    reg inside_dec,patch_dec;
    reg [7:0] wx_delay[0:2],wy_delay[0:2];
    reg [2:0] inside_delay;
    wire cache_valid;wire [15:0] p00,p01,p10,p11;
    patch_store u_patch(
        .clk(clk),.rst_n(rst_n),.load_valid(cache_load),.load_buffer(load_buffer),
        .load_y(load_row[7:0]),.load_word(load_beat[3:0]),.load_data(rd_data),
        .sample_valid(decode_valid),.sample_buffer(patch_dec),
        .x0(x0),.y0(y0),.x1(x1),.y1(y1),
        .out_valid(cache_valid),.p00(p00),.p01(p01),.p10(p10),.p11(p11)
    );
    wire interp_valid,interp_inside;wire [15:0] interp_pixel;
    bilinear_rgb u_interp(clk,rst_n,cache_valid,inside_delay[2],p00,p01,p10,p11,
                          wx_delay[2],wy_delay[2],interp_valid,interp_inside,interp_pixel);
    wire enhanced_valid;wire [15:0] enhanced_pixel;
    wire frame_begin=start_frame;
    adaptive_gamma u_enhance(
        .clk(clk),.rst_n(rst_n),.frame_begin(frame_begin),.frame_end(published),
        .enable(frame_cfg[14*32]),.in_valid(interp_valid),.in_inside(interp_inside),.in_pixel(interp_pixel),
        .out_valid(enhanced_valid),.out_pixel(enhanced_pixel),.mode(gamma_mode)
    );
    reg [31:0] output_mem[0:2047];
    reg [15:0] low_pixel;
    reg [1:0] output_full;
    reg [4:0] output_x[0:1];reg [5:0] output_y[0:1],output_h[0:1];
    // Production pixels never contain host metadata or diagnostic marks.
    wire [15:0] final_pixel=enhanced_pixel;
    function [31:0] smooth_word;
        input signed [31:0] current_value,target_value;
        reg signed [32:0] midpoint_sum;
        reg signed [31:0] midpoint;
        begin
            // The midpoint is algebraically current + (target-current)/2.
            // Keep the explicit progress rule so a one-LSB positive delta
            // cannot stall after fixed-point rounding.
            midpoint_sum={current_value[31],current_value}+
                         {target_value[31],target_value};
            midpoint=midpoint_sum>>>1;
            if(midpoint==current_value && target_value!=current_value)
                smooth_word=target_value;
            else smooth_word=midpoint;
        end
    endfunction
    wire smooth_enabled=cfg[14*32+3] ? cfg[14*32+1] : cfg[15*32+17];
    always @(posedge clk) begin
        if(render_issue) coordinate<=coordinates[{render_context,render_issued[10:0]}];
        if(coordinate_valid) begin
            x0<=coordinate[26:16]-min_x[render_context];
            y0<=coordinate[37:27]-min_y[render_context];
            x1<=coordinate[26:16]-min_x[render_context]+(coordinate[26:16]!=1919);
            y1<=coordinate[37:27]-min_y[render_context]+(coordinate[37:27]!=1079);
            wx_dec<=coordinate[7:0];wy_dec<=coordinate[15:8];
            inside_dec<=coordinate[38] && !empty[render_context];
            patch_dec<=patch_id[render_context];
        end
        wx_delay[0]<=wx_dec;wy_delay[0]<=wy_dec;
        wx_delay[1]<=wx_delay[0];wy_delay[1]<=wy_delay[0];
        wx_delay[2]<=wx_delay[1];wy_delay[2]<=wy_delay[1];
        if(enhanced_valid && render_active) begin
            low_pixel<=final_pixel;
            if(render_received[0])
                output_mem[{render_buffer,render_received[10:1]}]<={final_pixel,low_pixel};
        end
    end

    // Writeback worker. Output packets are always complete 64-pixel tile rows.
    localparam W_IDLE=0,W_ADDRESS=1,W_PREFETCH=2,W_SEND=3;
    reg [1:0] ws;
    reg write_buffer,next_write_buffer;
    reg [9:0] write_index,write_limit;
    reg [10:0] write_words;
    reg [23:0] write_address;
    reg [31:0] write_head;
    reg [10:0] written_tiles;
    assign wr_req=fs==F_RUN && ws==W_SEND;
    assign wr_addr=write_address;assign wr_data=write_head;
    always @(posedge clk) begin
        if(ws==W_PREFETCH) write_head<=output_mem[{write_buffer,10'd0}];
        else if(ws==W_SEND && wr_gnt)
            write_head<=output_mem[{write_buffer,write_index+10'd1}];
    end

    integer j;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            fs<=F_IDLE;busy<=0;pending<=0;have_src<=0;have_dst<=0;
            src_req<=0;src_rel<=0;slot_req<=0;source<=0;destination<=0;frame_cfg<=0;
            cycles<=0;read_wait<=0;write_wait<=0;read_beats<=0;invalid_pixels<=0;
            frame_count<=0;published_cfg<=0;have_published<=0;
            last_cycles<=0;last_rd_wait<=0;last_wr_wait<=0;
            last_read_beats<=0;last_invalid<=0;overflow_tiles<=0;protocol_fault<=0;
            map_active<=0;map_done<=0;map_cursor<=0;map_context<=0;
            next_tile_x<=0;next_tile_y<=0;map_issued<=0;map_received<=0;map_limit<=0;
            bound_min_x<=0;bound_min_y<=0;bound_max_x<=0;bound_max_y<=0;bound_any<=0;
            ls<=L_IDLE;load_cursor<=0;load_context<=0;load_buffer<=0;next_load_buffer<=0;
            patch_busy<=0;load_row<=0;load_beat<=0;rd_addr<=0;rd_len<=0;
            render_active<=0;render_cursor<=0;render_context<=0;render_buffer<=0;
            next_render_buffer<=0;render_issued<=0;render_received<=0;render_limit<=0;
            coordinate_valid<=0;decode_valid<=0;inside_delay<=0;
            output_full<=0;ws<=W_IDLE;write_buffer<=0;next_write_buffer<=0;
            write_index<=0;write_limit<=0;write_address<=0;written_tiles<=0;
            write_words<=0;all_written<=0;
            for(j=0;j<3;j=j+1) begin
                context_state[j]<=C_FREE;tile_x[j]<=0;tile_y[j]<=0;tile_h[j]<=0;
                min_x[j]<=0;min_y[j]<=0;max_y[j]<=0;patch_words[j]<=0;empty[j]<=1;patch_id[j]<=0;
            end
            for(j=0;j<2;j=j+1) begin output_x[j]<=0;output_y[j]<=0;output_h[j]<=0;end
        end else begin
            src_rel<=0;
            coordinate_valid<=render_issue;
            decode_valid<=coordinate_valid;
            inside_delay<={inside_delay[1:0],inside_dec};
            if(frame_update) pending<=1;
            if(busy) cycles<=cycles+1'b1;
            if(rd_req && !rd_gnt) read_wait<=read_wait+1'b1;
            if(ls==L_RETURN && !rd_valid) read_wait<=read_wait+1'b1;
            if(wr_req && !wr_gnt) write_wait<=write_wait+1'b1;
            if(rd_valid && ls==L_RETURN) read_beats<=read_beats+1'b1;
            if(map_valid && map_active && !map_inside) invalid_pixels<=invalid_pixels+1'b1;

            case(fs)
                F_IDLE: if(pending && !protocol_fault && !config_pending) begin
                    busy<=1;pending<=frame_update;frame_cfg<=cfg;
                    // Target updates and progression are independent. Continue
                    // progressing on every source frame between UART commands.
                    // First frame and ordinary/manual configurations are exact.
                    if(smooth_enabled && have_published && cfg[6*32+:9*32]==frame_cfg[6*32+:9*32])
                        for(j=0;j<6;j=j+1)
                            frame_cfg[j*32+:32]<=smooth_word(frame_cfg[j*32+:32],cfg[j*32+:32]);
                    src_req<=1;slot_req<=1;have_src<=0;have_dst<=0;
                    cycles<=0;read_wait<=0;write_wait<=0;read_beats<=0;invalid_pixels<=0;
                    fs<=F_ACQUIRE;
                end
                F_ACQUIRE: begin
                    if(src_req && src_gnt) begin source<=src_slot;src_req<=0;have_src<=1;end
                    if(slot_req && slot_gnt) begin destination<=slot;slot_req<=0;have_dst<=1;end
                    if(start_frame) fs<=F_RUN;
                end
                F_RUN: if(all_written) fs<=F_COMMIT;
                F_COMMIT: fs<=F_PUBLISH;
                F_PUBLISH: if(published) begin
                    src_rel<=1;fs<=F_RELEASE;frame_count<=frame_count+1'b1;
                    have_published<=1;published_cfg<=frame_cfg;
                    last_cycles<=cycles;last_rd_wait<=read_wait;last_wr_wait<=write_wait;
                    last_read_beats<=read_beats;last_invalid<=invalid_pixels;
                end
                F_RELEASE: begin busy<=0;fs<=F_IDLE;end
                default: ;
            endcase

            if(start_frame) begin
                map_active<=0;map_done<=0;map_cursor<=0;next_tile_x<=0;next_tile_y<=0;
                ls<=L_IDLE;load_cursor<=0;next_load_buffer<=0;patch_busy<=0;
                render_active<=0;render_cursor<=0;next_render_buffer<=0;
                output_full<=0;ws<=W_IDLE;next_write_buffer<=0;written_tiles<=0;all_written<=0;
                for(j=0;j<3;j=j+1) context_state[j]<=C_FREE;
            end else if(fs==F_RUN) begin
                if(!map_active && !map_done && context_state[map_cursor]==C_FREE) begin
                    map_active<=1;map_context<=map_cursor;context_state[map_cursor]<=C_MAP;
                    tile_x[map_cursor]<=next_tile_x;tile_y[map_cursor]<=next_tile_y;
                    tile_h[map_cursor]<=(next_tile_y==33)?6'd24:6'd32;
                    map_limit<=(next_tile_y==33)?12'd1536:12'd2048;
                    map_issued<=0;map_received<=0;bound_any<=0;
                    bound_min_x<=1920;bound_min_y<=1080;bound_max_x<=0;bound_max_y<=0;
                end
                if(map_in) map_issued<=map_issued+1'b1;
                if(map_active && map_valid) begin
                    map_received<=map_received+1'b1;
                    bound_min_x<=next_min_x;bound_min_y<=next_min_y;
                    bound_max_x<=next_max_x;bound_max_y<=next_max_y;
                    bound_any<=bound_any||map_inside;
                    if(map_received==map_limit-1'b1) begin
                        map_active<=0;context_state[map_context]<=C_MAPPED;
                        min_x[map_context]<={next_min_x[10:4],4'd0};
                        min_y[map_context]<={next_min_y[10:1],1'b0};
                        max_y[map_context]<=next_max_y;
                        patch_words[map_context]<=bounds_words[4:0];
                        empty[map_context]<=bounds_empty||bounds_overflow;
                        if(bounds_overflow) overflow_tiles<=overflow_tiles+1'b1;
                        map_cursor<=next_context(map_cursor);
                        if(next_tile_x==29) begin
                            next_tile_x<=0;
                            if(next_tile_y==33) map_done<=1;
                            else next_tile_y<=next_tile_y+1'b1;
                        end else next_tile_x<=next_tile_x+1'b1;
                    end
                end
                case(ls)
                    L_IDLE: if(context_state[load_cursor]==C_MAPPED && !patch_busy[next_load_buffer]) begin
                        load_context<=load_cursor;load_buffer<=next_load_buffer;
                        patch_id[load_cursor]<=next_load_buffer;
                        patch_busy[next_load_buffer]<=1;
                        load_row<=0;load_beat<=0;
                        if(empty[load_cursor]) begin
                            context_state[load_cursor]<=C_READY;
                            load_cursor<=next_context(load_cursor);next_load_buffer<=!next_load_buffer;
                        end else begin context_state[load_cursor]<=C_LOAD;ls<=L_ADDRESS;end
                    end
                    L_ADDRESS: begin
                        rd_addr<={2'd0,source,20'd0}+
                            row_word_address(11'd1079-min_y[load_context]-load_row)+
                            {14'd0,min_x[load_context][10:1]};
                        rd_len<={2'd0,patch_words[load_context]}-1'b1;
                        load_beat<=0;ls<=L_REQUEST;
                    end
                    L_REQUEST: if(rd_gnt) ls<=L_RETURN;
                    L_RETURN: if(rd_valid) begin
                        load_beat<=load_beat+1'b1;
                        if(rd_last!=(load_beat==patch_words[load_context]-1'b1)) protocol_fault<=1;
                        if(rd_last) begin
                            if(min_y[load_context]+load_row==max_y[load_context]) begin
                                context_state[load_context]<=C_READY;ls<=L_IDLE;
                                load_cursor<=next_context(load_cursor);next_load_buffer<=!next_load_buffer;
                            end else begin load_row<=load_row+1'b1;ls<=L_ADDRESS;end
                        end
                    end
                endcase
                if(!render_active && context_state[render_cursor]==C_READY && !output_full[next_render_buffer]) begin
                    render_active<=1;render_context<=render_cursor;context_state[render_cursor]<=C_RENDER;
                    render_buffer<=next_render_buffer;render_issued<=0;render_received<=0;
                    render_limit<={tile_h[render_cursor],6'd0};
                    output_x[next_render_buffer]<=tile_x[render_cursor];
                    output_y[next_render_buffer]<=tile_y[render_cursor];
                    output_h[next_render_buffer]<=tile_h[render_cursor];
                end
                if(render_issue) render_issued<=render_issued+1'b1;
                if(enhanced_valid && render_active) begin
                    render_received<=render_received+1'b1;
                    if(render_received==render_limit-1'b1) begin
                        render_active<=0;context_state[render_context]<=C_FREE;
                        patch_busy[patch_id[render_context]]<=0;
                        output_full[render_buffer]<=1;
                        render_cursor<=next_context(render_cursor);next_render_buffer<=!next_render_buffer;
                    end
                end
                case(ws)
                    W_IDLE: if(output_full[next_write_buffer]) begin
                        write_buffer<=next_write_buffer;write_index<=0;
                        write_limit<={output_h[next_write_buffer],5'd0}-1'b1;
                        ws<=W_ADDRESS;
                    end
                    W_ADDRESS: begin
                        write_address<={1'b0,destination,20'd0}+
                            row_word_address(11'd1079-{output_y[write_buffer],5'd0})+
                            {14'd0,output_x[write_buffer],5'd0};
                        ws<=W_PREFETCH;
                    end
                    W_PREFETCH: ws<=W_SEND;
                    W_SEND: if(wr_gnt) begin
                        write_index<=write_index+1'b1;
                        write_address<=write_index[4:0]==31 ? write_address-24'd991 : write_address+1'b1;
                        if(write_index==write_limit) begin
                            output_full[write_buffer]<=0;next_write_buffer<=!next_write_buffer;
                            written_tiles<=written_tiles+1'b1;ws<=W_IDLE;
                            if(written_tiles==1019) all_written<=1;
                        end
                    end
                endcase
            end
        end
    end
endmodule
