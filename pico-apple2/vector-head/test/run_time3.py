"""Timing for a typed sentence, with the delay loops running for real.

No pixel decoding here -- run3.py does that -- so this can afford the four
seconds of 6502 that the real delays cost.  The times each shape is DUE are
read out of fsound in memory, which the 6502 built itself, so this checks the
delays against the frame list rather than against a second opinion of it.
"""
import subprocess, sys
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

CLK = 1020484.0
sym = {}
for ln in open('../src/vhead.lbl'):
    p = ln.split()
    if len(p) == 3 and p[0] == 'al':
        sym[p[2].lstrip('.')] = int(p[1], 16)

TEXT = sys.argv[1] if len(sys.argv) > 1 else \
    "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG"

mem = ObservableMemory(); mpu = MPU(memory=mem)
card, flips, shown = [], [], [1]


keys = []


def kbd(addr, value=None):
    if addr == 0xC000:
        return (0x80 | keys[0]) if keys else 0
    if addr == 0xC010 and keys:
        keys.pop(0)
    return 0


def soft(addr, value=None):
    if addr in (0xC000, 0xC010):
        return kbd(addr)
    if addr in (0xC054, 0xC055):
        shown[0] = 1 if addr == 0xC054 else 2
        flips.append(mpu.processorCycles)
    return 0


for a in (0xC000, 0xC00C, 0xC050, 0xC051, 0xC052, 0xC053, 0xC054, 0xC055,
          0xC057, 0xC010):
    mem.subscribe_to_write([a], lambda addr, value: soft(addr))
    mem.subscribe_to_read([a], soft)
mem.subscribe_to_write([0xC0C0],
                       lambda addr, value: card.append((value, mpu.processorCycles)))
for i, b in enumerate(open('../src/vhead.bin', 'rb').read()):
    mem[0x6000 + i] = b
for i, b in enumerate(open('../src/nrldata.bin', 'rb').read()):
    mem[0x0C00 + i] = b
for a in (0xFDED, 0xFC58):
    mem[a] = 0x60
mem[sym['start']] = 0x4C                        # skip the demo sentence
mem[sym['start'] + 1] = sym['again'] & 0xFF
mem[sym['start'] + 2] = sym['again'] >> 8

pending = [TEXT]
mpu.pc = sym['start']; mpu.sp = 0xFF
n = 0
while n < 40_000_000:
    if mpu.pc == sym['getline'] and not keys and pending:
        keys.extend([ord(c) for c in pending.pop(0)] + [13])
    mpu.step(); n += 1
    if not pending and mpu.pc == sym['quit']:
        break

nf = mem[sym['nf']]
an = mem[sym['an']]
t0 = card[1][1]                                  # the first allophone byte
up = [(c - t0) / CLK * 1000 for c in flips if c > t0]
due = [(mem[sym['fsound'] + 2 * i] | (mem[sym['fsound'] + 2 * i + 1] << 8)) / 4.0
       for i in range(nf + 1)]

print('"%s"' % TEXT)
print('%d allophones, %d frames, %d instructions' % (an, nf, n))
print('burst send: %.1f ms' % ((card[an][1] - t0) / CLK * 1000))
errs = [up[i] - due[i] for i in range(min(nf, len(up)))]
print('sound ends at %.3f s; last shape up at %.3f s' % (due[nf] / 1000, up[nf - 1] / 1000))
print('per-shape sync error: worst %+.1f ms, mean %+.1f ms, |mean| %.1f ms'
      % (max(errs, key=abs), sum(errs) / len(errs),
         sum(abs(e) for e in errs) / len(errs)))
