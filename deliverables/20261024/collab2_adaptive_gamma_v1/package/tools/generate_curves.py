"""Generate synthesizable RGB565 Gamma tables, no runtime arithmetic IP."""
import argparse,math
from pathlib import Path
def render():
    exponents=(0.6,0.8,1.0,1.25,1.6)
    lines=['// 自动生成的静态Gamma曲线；公式见docs/设计说明.md。',
           'module adaptive_gamma_curve(input wire [2:0] i_curve,',
           ' input wire [15:0] i_pix, output wire [15:0] o_pix);']
    for name,bits,sel in [('r',5,'i_pix[15:11]'),('g',6,'i_pix[10:5]'),('b',5,'i_pix[4:0]')]:
        if name=='b':
            lines.append('assign o_pix[4:0] = map5({i_curve, i_pix[4:0]});');continue
        n=1<<bits
        lines += [f'function [{bits-1}:0] map{bits};',f' input [{bits+2}:0] address;', ' begin', '  case(address)']
        for c,gamma in enumerate(exponents):
            for x in range(n):
                x8=(x<<3|x>>2) if bits==5 else (x<<2|x>>4)
                y=int(math.floor(255*(x8/255)**gamma+0.5))>>(8-bits)
                lines.append(f"   {bits+3}'d{c*n+x}: map{bits} = {bits}'d{y};")
        lines += [f"   default: map{bits} = address[{bits-1}:0];",'  endcase',' end','endfunction']
        lines.append(f'assign o_pix[{"15:11" if bits==5 else "10:5"}] = map{bits}({{i_curve, {sel}}});')
    lines.append('endmodule')
    return '\n'.join(lines)+'\n'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Output exists; select a new path')
    a.out.write_text(render(),encoding='utf-8')
