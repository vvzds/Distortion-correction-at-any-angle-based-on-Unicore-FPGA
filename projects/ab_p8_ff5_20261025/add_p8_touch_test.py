from pathlib import Path
import shutil
R=Path(r'C:\Users\lenovo\Desktop\ww\AB_P8触摸译码局部化_20261025')
(R/'tests/p8_touch_exhaustive_tb.sv').write_text('''`timescale 1ns/1ps
module p8_touch_exhaustive_tb;
reg clk=0;always #4 clk=~clk;
reg rst_n=0,clear=0,touch=0;
reg [31:0] ids=0;
reg [21:0] seq=0;
undistort_cache_ab dut(.clk(clk),.rst_n(rst_n),.i_frame_clear(clear),.i_line_mode(1'b0),
 .i_load_begin(1'b0),.i_load_bank(8'd0),.i_load_row(11'd0),.i_load_vld(1'b0),.i_load_last(1'b0),.i_load_data(256'd0),
 .i_query_row_a(11'd0),.i_query_row_b(11'd0),.i_prefetch_row(11'd0),
 .i_sample_req(1'b0),.i_sample_bank_a(8'd0),.i_sample_bank_b(8'd0),.i_sample_bank_a1(8'd0),.i_sample_bank_b1(8'd0),.i_sample_x(11'd0),
 .i_lookup_req(1'b0),.i_lookup_a(11'd0),.i_lookup_b(11'd0),.i_lookup_x(11'd0),.i_lookup_seq(22'd0),
 .i_touch(touch),.i_touch_ids(ids),.i_touch_seq(seq),.i_retired_count(22'd0),.i_ready_ids(32'd0),.i_fetch_gnt(1'b0));
reg [191:0] expected;
reg [21:0] ages[0:191];
integer lane,id,en,s,checks=0,seed=32'h375ba927;
task check_update;
begin
 #1;expected=0;
 for(s=0;s<4;s=s+1)if(touch && ids[s*8+:8]<192)expected[ids[s*8+:8]]=1'b1;
 if(dut.age_touch_mask!==expected)$fatal(1,"touch mask mismatch ids=%h touch=%b",ids,touch);
 @(posedge clk);
 if(rst_n && !clear)for(s=0;s<192;s=s+1)if(expected[s])ages[s]=seq;
 #1;for(s=0;s<192;s=s+1)if(dut.last_use[s]!==ages[s])$fatal(1,"touch timestamp mismatch slot=%0d ids=%h",s,ids);
 checks=checks+1;
end endtask
initial begin
 for(s=0;s<192;s=s+1)begin dut.last_use[s]=0;ages[s]=0;end
 repeat(2)@(negedge clk);rst_n=1;
 // Include invalid 192..255 IDs; each lane must independently decode all slots.
 for(lane=0;lane<4;lane=lane+1)for(id=0;id<256;id=id+1)for(en=0;en<2;en=en+1)begin
  @(negedge clk);ids=32'hffffffff;ids[lane*8+:8]=id;touch=en;seq=seq+1;check_update;
 end
 // Duplicate IDs, independently mixed banks, and reset/frame-clear suppression.
 for(id=0;id<192;id=id+1)begin
  @(negedge clk);ids={4{id[7:0]}};touch=1;seq=seq+1;check_update;
 end
 for(id=0;id<512;id=id+1)begin
  @(negedge clk);ids=$random(seed);touch=id%3!=0;clear=id%13==0;rst_n=id%17!=0;seq=seq+1;check_update;
 end
 $display("P8_TOUCH_EXHAUSTIVE PASS checks=%0d lanes=4 ids_per_lane=256 enable_values=2 duplicates=192 mixed=512",checks);$finish;
end
initial begin #100000;$fatal(1,"watchdog");end
endmodule
''',encoding='utf-8')
(R/'run_touch_test.py').write_text('''from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parent;O=R/'results/touch_exhaustive';O.mkdir(parents=True,exist_ok=False)
T=Path(r'C:\\Users\\lenovo\\Documents\\Codex\\2026-10-11\\w-m\\work\\simulator\\iverilog\\app')
drive=next(c+':' for c in 'YXWVUTSRQP' if not Path(c+':/').exists());subprocess.run(['subst',drive,str(T)],check=True)
files=[R/'tests/p8_touch_exhaustive_tb.sv',R/'candidate/source/rtl/undistort_cache_ab.v']
before={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
commands=[[drive+'/bin/iverilog.exe','-B',drive+'/lib/ivl','-g2012','-s','p8_touch_exhaustive_tb','-o',str(O/'sim.vvp')]+[str(p) for p in files],[drive+'/bin/vvp.exe',str(O/'sim.vvp')]]
steps=[]
try:
 for cmd,name in zip(commands,['compile','simulation']):
  with (O/(name+'.log')).open('wb') as f:rc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=90).returncode
  steps.append(dict(argv=cmd,exit_code=rc))
  if rc:break
finally:subprocess.run(['subst',drive,'/D'],check=True)
after={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
text=(O/'simulation.log').read_text(errors='replace') if (O/'simulation.log').exists() else ''
result=dict(passed=len(steps)==2 and all(s['exit_code']==0 for s in steps) and 'P8_TOUCH_EXHAUSTIVE PASS checks=2752' in text and before==after,steps=steps,inputs_before=before,inputs_after=after,log=text)
(O/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(text);raise SystemExit(0 if result['passed'] else 1)
''',encoding='utf-8')
shutil.copy2(__file__,R/'add_p8_touch_test.py')
