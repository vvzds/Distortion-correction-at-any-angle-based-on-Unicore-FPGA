"""Extend the unchanged equivalence monitor with all-bank public allocation cases."""
from pathlib import Path
R=Path(__file__).resolve().parent
p=R/'tests/cache_p7_equivalence_tb.sv';s=p.read_text(encoding='utf-8')
anchor='    $display("P7_EQUIVALENCE PASS tests='
i=s.index(anchor)
extra='''    // P7B01: all 192 physical slots, including every bank/parity/address boundary.
    // Only the target is eligible; use the PUBLIC allocation/write/fetch path.
    for(n=0;n<192;n=n+1)begin
        reset_both;i_retired_count=22'h3fffff;
        for(j=0;j<192;j=j+1)slot(j,1300+j,j%30,1,1);
        slot(n,1300+n,n%30,0,0);
        request(((n*34)%1078)+(n%2),((n*34)%1078)+(n%2),(n%30)*64+4,1000+n);
        finish_lookup;
        if(selected_ids!=={4{n[7:0]}})$fatal(1,"bank allocation target=%0d actual=%h",n,selected_ids);
        if(!dut.o_fetch_req || dut.o_fetch_bank!==n[7:0] ||
           dut.o_fetch_row!==(((n*34)%1078)+(n%2)) || dut.o_fetch_seg!==(n%30))
            $fatal(1,"bank fetch decode target=%0d row=%0d seg=%0d",n,dut.o_fetch_row,dut.o_fetch_seg);
        i_fetch_gnt=1;tick;i_fetch_gnt=0;
        i_load_begin=1;i_load_bank=n;i_load_row=((n*34)%1078)+(n%2);tick;i_load_begin=0;
        for(j=0;j<4;j=j+1)begin
            load_pattern=32'h5a000000+n*4+j;
            i_load_vld=1;i_load_last=j==3;i_load_data={8{load_pattern}};tick;
        end
        i_load_vld=0;i_load_last=0;tick;
        i_ready_ids={4{n[7:0]}};#1;
        if(!dut.o_ids_ready)$fatal(1,"bank ready target=%0d",n);
        request(((n*34)%1078)+(n%2),((n*34)%1078)+(n%2),(n%30)*64+4,2000+n);
        finish_lookup;
        if(selected_ids!=={4{n[7:0]}})$fatal(1,"bank repeat hit target=%0d",n);
    end
    // P7B02: intentionally duplicate keys: largest slot and largest bank win.
    for(n=0;n<24;n=n+1)begin
        reset_both;
        for(j=0;j<8;j=j+1)slot(16*(n/2)+2*j+(n%2),20+(n%2),3,1,0);
        request(20+(n%2),20+(n%2),3*64+4,3000+n);finish_lookup;
        if(selected_ids!=={4{(8'd16*(n/2)+8'd14+(n%2))}})
            $fatal(1,"bank local priority bank/parity=%0d actual=%h",n,selected_ids);
    end
    for(n=0;n<2;n=n+1)begin
        reset_both;
        for(j=0;j<96;j=j+1)slot(2*j+n,20+n,3,1,0);
        request(20+n,20+n,3*64+4,4000+n);finish_lookup;
        if(selected_ids!=={4{(8'd190+n)}})$fatal(1,"global bank priority parity=%0d actual=%h",n,selected_ids);
    end
    $display("P7_BANK_COVERAGE PASS slots=192 public_alloc=192 fetch=192 public_load=192 repeat_hit=192 local_priority=24 global_priority=2");
'''
extra=extra.replace('{4{(8\'d16*(n/2)+8\'d14+(n%2))}}','{4{expected_slot}}').replace('{4{(8\'d190+n)}}','{4{expected_slot}}')
extra=extra.replace('        if(selected_ids!=={4{expected_slot}})','        expected_slot=16*(n/2)+14+(n%2);\n        if(selected_ids!=={4{expected_slot}})',1)
pos=extra.rindex('        if(selected_ids!=={4{expected_slot}})');extra=extra[:pos]+'        expected_slot=190+n;\n'+extra[pos:]
s=s[:i]+extra+s[i:];s=s.replace('reg [31:0] selected_ids;','reg [31:0] selected_ids;\nreg [7:0] expected_slot;\nreg [31:0] load_pattern;')
s=s.replace('cache_p7_equivalence_tb','cache_p7_banks_tb').replace('P7_EQUIVALENCE','P7_BANKS_EQUIVALENCE')
(R/'tests/cache_p7_banks_tb.sv').write_text(s,encoding='utf-8')
runner=(R/'run_equivalence.py').read_text(encoding='utf-8')
a=runner.index('cases=[');b=runner.index('\ndef run',a)
runner=runner[:a]+"cases=[('banks','cache_p7_banks_tb.sv','cache_p7_banks_tb','P7_BANKS_EQUIVALENCE PASS')]"+runner[b:]
runner=runner.replace("out=R/'results/equivalence_p7'", "out=R/'results/banks_p7'")
(R/'run_bank_tests.py').write_text(runner,encoding='utf-8')
