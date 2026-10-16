"""The face, the thirteen shapes, and what each copy costs.

Everything here is checked by decoding $2000/$4000 through HGR's own interleave
and comparing against the PC rasteriser pixel for pixel -- the same rasteriser
that generated the stored bitmaps, so a disagreement means the 6502 is putting
them somewhere other than where they were cut from.

The two cycle counts are not decoration: run-time timing subtracts them, so
they are measured here and written into anim.inc as MOUTH4 and EYE4.

run3.py checks the frames of an actual sentence; this one checks the pieces.
"""
import io, contextlib, importlib.util, os
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

sym = {}
for ln in open('../src/vhead.lbl'):
    p = ln.split()
    if len(p) == 3 and p[0] == 'al':
        sym[p[2].lstrip('.')] = int(p[1], 16)

mem = ObservableMemory()
mpu = MPU(memory=mem)
card, flips, shown = [], [], [1]


def soft(addr, value=None):
    if addr == 0xC054:
        shown[0] = 1; flips.append(1)
    elif addr == 0xC055:
        shown[0] = 2; flips.append(2)
    return 0


for a in (0xC000, 0xC00C, 0xC050, 0xC051, 0xC052, 0xC053, 0xC054, 0xC055,
          0xC057, 0xC010):
    mem.subscribe_to_write([a], lambda addr, value: soft(addr))
    mem.subscribe_to_read([a], soft)
mem.subscribe_to_write([0xC0C0], lambda addr, value: card.append(value))

for i, b in enumerate(open('../src/vhead.bin', 'rb').read()):
    mem[0x6000 + i] = b

spec = importlib.util.spec_from_file_location('mkm', '../tools/mkmouth_a2.py')
mkm = importlib.util.module_from_spec(spec)
here = os.getcwd(); os.chdir('..')
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(mkm)
os.chdir(here)

CLK = 1020484.0


def hgr(base):
    px = [[0] * 280 for _ in range(192)]
    for y in range(192):
        a = base + 0x400 * (y & 7) + 0x80 * ((y >> 3) & 7) + 40 * (y >> 6)
        for b in range(40):
            v = mem[a + b]
            for bit in range(7):
                if v & (1 << bit):
                    px[y][b * 7 + bit] = 1
    return px


def want(v, e):
    return [[m | y for m, y in zip(rm, re)]
            for rm, re in zip(mkm.shapes[v], mkm.eyes[e])]


def diff(a, b):
    return sum(1 for y in range(192) for x in range(280) if a[y][x] != b[y][x])


# ---- 1. init: the face, drawn once, on both pages ------------------------
mem[sym['msg_demo']] = 0                        # straight to the prompt
mem[sym['delay2']] = 0x60
for a in (0xFDED, 0xFC58):                      # COUT and HOME: nothing here
    mem[a] = 0x60                               # implements them, and an
                                                # unimplemented $FDED is a BRK
mpu.pc = sym['start']
n = 0
while mpu.pc != sym['getline'] and n < 4_000_000:
    mpu.step(); n += 1
p1, p2 = hgr(0x2000), hgr(0x4000)
print('init: %d cycles (%.0f ms)' % (mpu.processorCycles,
                                     mpu.processorCycles / CLK * 1000))
print('page 1 == page 2        : %s' % (p1 == p2))
print('page 1 vs the PC raster : %d pixels differ' % diff(p1, want(0, 0)))
print('lit pixels              : %d' % sum(sum(r) for r in p1))

# ---- 2. what each copy costs ---------------------------------------------
for name, n_shapes, label in (('blit_mouth', 10, 'mouth'), ('blit_eye', 3, 'eye')):
    mem[sym['hidden']] = 0x20
    mpu.a, mpu.x, mpu.y = 0, 1, 0
    mpu.pc = sym[name]; mpu.sp = 0xFD
    c0 = mpu.processorCycles; k = 0
    while k < 200000:
        mpu.step(); k += 1
        if mpu.sp > 0xFD: break
    print('%-10s: %5d cycles = %.3f ms'
          % (name, mpu.processorCycles - c0, (mpu.processorCycles - c0) / CLK * 1000))

# ---- 3. every shape, against the PC raster -------------------------------
_p1 = hgr(0x2000); _w = want(0, 0)
_d = [(x, y) for y in range(192) for x in range(280) if _p1[y][x] != _w[y][x]]
print('page 1 before the per-shape checks: %d pixels differ; rows %s cols %s'
      % (len(_d), sorted({y for _, y in _d})[:6], sorted({x for x, _ in _d})[:6]))
print('  hidden symbol at $%04X, value $%02X' % (sym['hidden'], mem[sym['hidden']]))
bad = 0
for grp, n_sh, other in (('blit_mouth', 10, 'blit_eye'), ('blit_eye', 3, 'blit_mouth')):
    for i in range(n_sh):
        mem[sym['hidden']] = 0x00
        for nm, idx in ((grp, i), (other, 0)):
            mpu.a, mpu.x, mpu.y = 0, idx, 0
            mpu.pc = sym[nm]; mpu.sp = 0xFD
            k = 0
            while k < 200000:
                mpu.step(); k += 1
                if mpu.sp > 0xFD: break
        d = diff(hgr(0x2000), want(i, 0) if grp == 'blit_mouth' else want(0, i))
        bad += d
        if d:
            print('  %s %d: %d pixels differ' % (grp, i, d))
print('all 13 shapes against the PC raster: %d pixels differ in total' % bad)
