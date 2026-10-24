"""Independent frame-level reference. Does not import RTL table generator."""
import math, random, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXP=(0.60,0.80,1.00,1.25,1.60)
def channels(p):
    r,g,b=(p>>11)&31,(p>>5)&63,p&31
    return (r*8+r//4,g*4+g//16,b*8+b//4)
def corrected(p,c):
    out=[int(math.floor(255*math.pow(v/255,EXP[c])+0.5)) for v in channels(p)]
    return ((out[0]//8)<<11)|((out[1]//4)<<5)|(out[2]//8)
def gray(v): return ((v//8)<<11)|((v//4)<<5)|(v//8)
def next_curve(current,pixels):
    mean=sum((r+2*g+b+2)//4 for r,g,b in map(channels,pixels))/len(pixels)
    # Each current-state interval is specified in the design table.
    lower=(float('-inf'),56,88,152,184)[current]
    upper=(72,104,168,200,float('inf'))[current]
    return current-1 if mean<lower else current+1 if mean>=upper else current

def main():
    rng=random.Random(20261024)
    f=(ROOT/'sim/vectors.mem').open('w',encoding='ascii')
    cases=[]; n=0; pending=2;active=2;enabled=False
    def emit(p=0,v=0,sop=0,eop=0,sof=0,eof=0,en=1,rst=1):
        nonlocal n,pending,active,enabled
        if not rst: pending=active=2;enabled=False
        if rst and v and sof: active=pending;enabled=bool(en)
        expected=corrected(p,active) if enabled else p
        word=p|(v<<16)|(sop<<17)|(eop<<18)|(sof<<19)|(eof<<20)|(en<<21)|(rst<<22)
        word|=((expected if rst else 0)<<23)|((v if rst else 0)<<39)
        f.write(f'{word:016x}\n'); n+=1
    def frame(label,pixels,en=1,bubbles=False,toggle=False,damage=None):
        nonlocal pending
        begin=n;before=pending
        length=len(pixels)
        for i,p in enumerate(pixels):
            if bubbles and rng.randrange(4)==0:
                # 无效拍标志和开关必须忽略。
                emit(rng.randrange(65536),sof=1,eof=1,en=1-en)
            eop=int(i%8==7); eof=int(i==length-1)
            if damage=='eop' and i==7: eop=0
            if damage=='no_eof': eof=0
            emit(p,1,int(i%8==0),eop,int(i==0),eof,
                 1-en if toggle and i>0 else en)
        if length==32 and damage is None: pending=next_curve(before,pixels)
        cases.append(dict(name=label,first_vector=begin,last_vector=n-1,
                          applied_curve=before,next_curve=pending))
    emit(rst=0);emit(rst=0);emit()
    for v in (32,32,32,64,64,80,112,140,180,220,220,190,160,128,80,32):
        frame(f'illumination_{v}_{len(cases)}',[gray(v)]*32,bubbles=True)
    for state in range(5):
        # force the reference to each curve through valid dark/bright frames
        target=0 if state<2 else 4
        for j in range(5): frame(f'prepare_{state}_{j}',[gray(32 if target==0 else 224)]*32)
        frame(f'random_rgb_{state}',[rng.randrange(65536) for _ in range(32)],toggle=True)
    for label,kw in [('early_eof',{'pixels':[gray(240)]*7}),
                     ('missing_eop',{'pixels':[gray(240)]*32,'damage':'eop'}),
                     ('missing_eof',{'pixels':[gray(240)]*32,'damage':'no_eof'}),
                     ('excess_pixels',{'pixels':[gray(240)]*40})]:
        frame(label,**kw)
        frame(label+'_recover',[gray(96)]*32)
    frame('bypass_midframe_toggle',[0x2492]*32,en=0,toggle=True)
    frame('enable_midframe_toggle',[0x2492]*32,en=1,toggle=True)
    frame('partial_before_reset',[gray(32)]*10,damage='no_eof')
    emit(rst=0)
    frame('reset_identity_first',[0x2492]*32)
    # 精确阈值两侧及黑白图，确保不会除零。
    for v in (0,255,55,56,71,72,87,88,103,104,151,152,167,168,183,184,199,200):
        frame('boundary_'+str(v),[gray(v)]*32)
    # 精确构造亮度阈值，不用灰度编码近似代替阈值本身。
    by_luma={}
    for p in range(65536):
        r,g,b=channels(p); y=(r+2*g+b+2)//4
        if y not in by_luma:by_luma[y]=p
    for c,thresholds in enumerate(((72,),(56,104),(88,168),(152,200),(184,))):
        for t in thresholds:
            for delta in (-1,0,1):
                while pending!=c:
                    frame(f'prepare_exact_{c}_{t}_{delta}_{pending}',[gray(32 if pending>c else 224)]*32)
                frame(f'exact_luma_state{c}_value{t+delta}',[by_luma[t+delta]]*32)
    emit();f.close()
    (ROOT/'evidence/vector_cases.json').write_text(json.dumps(dict(vectors=n,cases=cases),indent=2),encoding='utf-8')
    print(f'Generated {n} vectors / {len(cases)} cases')
if __name__=='__main__':main()
