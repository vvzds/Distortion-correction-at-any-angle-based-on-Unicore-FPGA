"""Golden-model and ModelSim checks for the Q20 projective divider."""
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from run_sim import run

Q20 = 1 << 20
SEEDS = [1973790,1766023,1597830,1458888,1342177,1242757,1157049,
         1082401,1016801,958698,906877,860370,818401,780336,745654,713924]


def reciprocal_fixed(denominator):
    index = min((denominator-Q20//2) >> 16, 15)
    reciprocal = SEEDS[index]
    reciprocal = (reciprocal*(2*Q20-((denominator*reciprocal) >> 20))) >> 20
    return (reciprocal*(2*Q20-((denominator*reciprocal) >> 20))) >> 20


def map_fixed(x, y, g0, g1):
    denominator = Q20 + ((g0*x + g1*y) >> 14)
    if not Q20//2 <= denominator <= Q20*3//2:
        return 0, 0, 0
    reciprocal = reciprocal_fixed(denominator)
    ox,oy=(x*reciprocal) >> 20,(y*reciprocal) >> 20
    ok=abs(ox)<=int(1.5*Q20) and abs(oy)<=int(1.5*Q20)
    return ox,oy,int(ok)


def main():
    rng = np.random.default_rng(20261101)
    count = 4096
    xy = rng.integers(-int(1.45*Q20), int(1.45*Q20)+1, (count, 2), dtype=np.int64)
    slopes = rng.integers(-int(.22*(1<<14)), int(.22*(1<<14))+1,
                          (count, 2), dtype=np.int64)
    cases = [(int(x), int(y), int(a), int(b))
             for (x,y),(a,b) in zip(xy,slopes)]
    cases += [(0,0,0,0),(Q20,0,0,0),(-Q20,0,0,0),
              (Q20,Q20,819,819),(Q20,Q20,-819,-819),
              (Q20,Q20,8192,8192),(Q20,Q20,-8192,-8192)]
    max_error_lsb = 0.
    for index in range(16):
        for offset in range(257):
            denominator = Q20//2 + index*65536 + offset*256
            reciprocal = reciprocal_fixed(denominator)
            for coordinate in (-int(1.5*Q20), int(1.5*Q20)):
                actual = (coordinate*reciprocal) >> 20
                exact = coordinate*Q20/denominator
                max_error_lsb = max(max_error_lsb, abs(actual-exact))
    if max_error_lsb > 40:
        raise AssertionError(f'Reciprocal approximation error {max_error_lsb:.2f} Q20 LSB')
    vectors = ROOT/'build'/'vectors'/'projective_divide.txt'
    vectors.parent.mkdir(parents=True,exist_ok=True)
    with vectors.open('w',encoding='ascii',newline='\n') as stream:
        for x,y,g0,g1 in cases:
            ox,oy,ok=map_fixed(x,y,g0,g1)
            stream.write(f'{x & 0xffffff:06x} {y & 0xffffff:06x} '
                         f'{g0 & 0xffff:04x} {g1 & 0xffff:04x} '
                         f'{ox & 0xffffff:06x} {oy & 0xffffff:06x} {ok}\n')
    folder=run('projective_divide_tb',
               ['source/rtl/projective_divide.v','sim/projective_divide_tb.v'],
               ['+VECTORS=build/vectors/projective_divide.txt'])
    print(f'PASS Q20 projective divide: {len(cases)} cases, '
          f'max error {max_error_lsb:.2f} normalized Q20 LSB; evidence: {folder}')


if __name__=='__main__':
    main()
