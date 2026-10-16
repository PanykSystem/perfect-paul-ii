"""Does the head blink while it is waiting for someone to type?

It did not, which is what prompted this: build_frames blinks off the sentence's
own clock, so with the head permanently on screen it sat motionless between
sentences.  getline now runs its own blink on a 2 ms poll tick.

delay2 is stubbed here, which costs nothing: a tick is one pass of the poll
loop whatever the delay actually takes, and that the delay really is 2 ms is
cal_delay.py's business, not this one's.
"""
from py65.devices.mpu6502 import MPU
from py65.memory import ObservableMemory

sym = {}
for ln in open('../src/vhead.lbl'):
    p = ln.split()
    if len(p) == 3 and p[0] == 'al':
        sym[p[2].lstrip('.')] = int(p[1], 16)

mem = ObservableMemory(); mpu = MPU(memory=mem)
flips, eyes = [], []


def soft(addr, value=None):
    if addr in (0xC054, 0xC055):
        flips.append(mpu.processorCycles)
    return 0


for a in (0xC000, 0xC00C, 0xC050, 0xC051, 0xC052, 0xC053, 0xC054, 0xC055,
          0xC057, 0xC010):
    mem.subscribe_to_write([a], lambda addr, value: soft(addr))
    mem.subscribe_to_read([a], soft)
mem.subscribe_to_write([0xC0C0], lambda addr, value: None)
mem.subscribe_to_write([sym['cureye'], sym['cureye'] + 1],
                       lambda addr, value: eyes.append((value, len(flips))))

for i, b in enumerate(open('../src/vhead.bin', 'rb').read()):
    mem[0x6000 + i] = b
for i, b in enumerate(open('../src/nrldata.bin', 'rb').read()):
    mem[0x0C00 + i] = b
for a in (0xFDED, 0xFC58):
    mem[a] = 0x60
mem[sym['delay2']] = 0x60
mem[sym['msg_demo']] = 0                        # straight to the prompt

mpu.pc = sym['start']; mpu.sp = 0xFF
n, ticks = 0, 0
while n < 30_000_000 and ticks < 12000:
    mpu.step(); n += 1
    if mpu.pc == sym['idle_blink']:
        ticks += 1

names = {0: 'open', 1: 'half', 2: 'shut'}
seq = [e for e, _ in eyes]
print('%d poll ticks at the prompt (%d ticks = 1 second)' % (ticks, 500))
print('eye changes: %d' % len(seq))
print('sequence: %s' % ' '.join(names.get(e, '?%d' % e) for e in seq[:20]))
blinks = sum(1 for a, b, c in zip(seq, seq[1:], seq[2:])
             if (a, b, c) == (1, 2, 1))
print('complete blinks (half-shut-half): %d in %.1f simulated seconds'
      % (blinks, ticks / 500.0))
print('page flips during the wait: %d' % len(flips))
