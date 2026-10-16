"""How long delay2 really waits, measured rather than counted.

The comment in the first draft said 186 iterations of an 11-cycle loop is 2046
cycles against the 2041 that 2 ms wants -- a quarter of a percent.  It left out
the loop's own ldx/dey/bne, which is another 6, so the real figure was 2052 and
the error half a percent.  Over the 1930 units of one sentence that is 21 ms,
which is exactly the sort of thing that is invisible on paper and obvious on a
screen.  So: measure, fit, and let the generator use the fit.
"""
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

sym = {}
for ln in open('../src/vhead.lbl'):
    p = ln.split()
    if len(p) == 3 and p[0] == 'al':
        sym[p[2].lstrip('.')] = int(p[1], 16)
mem = ObservableMemory(); mpu = MPU(memory=mem)
for i, b in enumerate(open('../src/vhead.bin', 'rb').read()):
    mem[0x6000 + i] = b

CLK = 1020484.0
pts = []
for a in (0, 1, 2, 50, 100, 200, 255):
    mpu.pc = sym['delay2']; mpu.a = a; mpu.sp = 0xFD
    c0 = mpu.processorCycles; k = 0
    while k < 2_000_000:
        mpu.step(); k += 1
        if mpu.sp > 0xFD: break
    c = mpu.processorCycles - c0
    pts.append((a, c))
    print('A=%3d  %7d cycles  %8.3f ms  (%.4f ms per unit)'
          % (a, c, c / CLK * 1000, (c / CLK * 1000 / a) if a else 0))
(a1, c1), (a2, c2) = pts[-2], pts[-1]
per = (c2 - c1) / (a2 - a1)
fixed = c1 - per * a1
print('\nfit: %.1f cycles a unit + %.1f fixed' % (per, fixed))
print('     %.4f ms a unit; 2 ms wants %.1f cycles' % (per / CLK * 1000, CLK * 0.002))
