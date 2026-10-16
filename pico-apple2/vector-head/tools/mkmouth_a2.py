"""Pre-render the moving parts as HGR bitmaps.

Drawing a shape with Bresenham at run time costs 279 ms a change on a 1 MHz
6502 -- measured, not estimated: 140 ms to draw and as much again to rub the
old one out.  Over a sentence that is 12.6 s of drawing against 3.9 s of
speech, which is why the first cut ran at a quarter speed with the voice
trailing behind it.

So do the drawing here.  Each shape is rasterised once, composited over the
static face, and the rectangle it moves in is kept as raw HGR bytes.  At run
time a change is then a block copy, and the old-shape-removal step disappears
entirely because the rectangle carries the face with it.

The compositing is OR, not EOR.  The CPC EORs the mouth because EOR is how you
rub something out without keeping a copy of what was under it -- and the price
is that every crossing with the face cancels, so between 26 and 44 face pixels
wink out, and a DIFFERENT set of them for each shape, which reads as dust
crawling over the face as it talks.  Nothing here needs rubbing out, so nothing
here needs EOR, and the face stays whole.

mkhead.py has TWO moving groups -- GROUPS = [(MOUTH + CHIN), (EYE)] -- and both
are cut out of `static`.  The first cut emitted only shapes[0], so the eye
sockets had nothing drawn in them at all.  Both are emitted now, each with its
own rectangle, because they are far apart and one rectangle spanning both would
be most of the face.

The rasteriser must agree with vhead.s pixel for pixel, or a stored rectangle
would not line up with the face drawn around it, so `line` below is a
transcription of `line` there rather than any Bresenham.
"""
import re

CX = 140
import os
HERE = os.path.dirname(os.path.abspath(__file__))
SRCDIR = os.path.join(HERE, '..', 'src')
SRC = os.path.join(SRCDIR, 'headdata_a2.inc')
NAMES = ['rest', 'shut', 'small', 'mid', 'wide', 'ee', 'oo', 'oh', 'fv', 'th']
ENAMES = ['open', 'half', 'shut']

src = open(SRC).read()


def lists(label):
    """The (dx,row) polylines stored under one label."""
    m = re.search(r'^' + label + r':.*?\n(.*?)(?=^\w|\Z)', src, re.S | re.M)
    vals = []
    for ln in m.group(1).splitlines():
        ln = ln.split(';')[0].strip()
        if ln.startswith('.byte'):
            vals += [int(x) for x in ln[5:].split(',')]
    i, polys = 0, []
    while i < len(vals):
        n = vals[i]
        i += 1
        if n == 0:
            break
        pts = []
        for _ in range(n):
            pts.append((vals[i], vals[i + 1]))
            i += 2
        polys.append(pts)
    return polys


def line(page, x0, y0, x1, y1):
    """vhead.s `line', transcribed.  err is dx-dy and e2 is taken once."""
    dx, sx = abs(x1 - x0), (1 if x1 >= x0 else -1)
    dy, sy = abs(y1 - y0), (1 if y1 >= y0 else -1)
    err = dx - dy
    while True:
        page[y0][x0] = 1
        if x0 == x1 and y0 == y1:
            return
        e2 = 2 * err
        if e2 + dy > 0:
            err -= dy
            x0 += sx
        if e2 - dx < 0:
            err += dx
            y0 += sy


def draw(page, polys):
    for side in (0, 1):                      # left half, then right
        for p in polys:
            pts = [((CX - dx) if side == 0 else (CX + dx), y) for dx, y in p]
            for a, b in zip(pts, pts[1:]):
                line(page, a[0], a[1], b[0], b[1])


blank = lambda: [[0] * 280 for _ in range(192)]

static = blank()
draw(static, lists('head_static'))


def composite(prefix, names):
    out = []
    for nm in names:
        pg = [row[:] for row in static]
        draw(pg, lists(prefix + nm))
        out.append(pg)
    return out


shapes = composite('mouth_', NAMES)
eyes = composite('eye_', ENAMES)


def rect(group):
    """The rectangle a group's shapes differ in.

    Every shape carries fixed lines -- the jaw, the brow -- so that it
    composites; those are identical in all of them, so what sets the size is
    comparing the shapes against EACH OTHER, not against the face.
    """
    rows = [y for y in range(192) if any(group[0][y] != s[y] for s in group[1:])]
    cols = [x for x in range(280)
            if any(group[0][y][x] != s[y][x] for s in group[1:] for y in rows)]
    y0, y1 = min(rows), max(rows)
    b0, b1 = min(cols) // 7, max(cols) // 7
    return b0, b1 - b0 + 1, y0, y1 - y0 + 1


MCOL, MW, MROW, MH = rect(shapes)
ECOL, EW, EROW, EH = rect(eyes)
assert MROW >= EROW + EH or EROW >= MROW + MH, 'the rectangles overlap'


def hgr_bytes(pg, col, w, row, h):
    out = bytearray()
    for y in range(row, row + h):
        for b in range(col, col + w):
            v = 0
            for bit in range(7):
                if pg[y][b * 7 + bit]:
                    v |= 1 << bit
            out.append(v)
    return out


if __name__ == '__main__':
    print('mouth: cols %d..%d rows %d..%d -> %dx%d = %d bytes x %d = %d'
          % (MCOL, MCOL + MW - 1, MROW, MROW + MH - 1, MW, MH, MW * MH,
             len(NAMES), MW * MH * len(NAMES)))
    print('eyes : cols %d..%d rows %d..%d -> %dx%d = %d bytes x %d = %d'
          % (ECOL, ECOL + EW - 1, EROW, EROW + EH - 1, EW, EH, EW * EH,
             len(ENAMES), EW * EH * len(ENAMES)))

    with open(os.path.join(SRCDIR, 'mouthdim_a2.inc'), 'w') as f:
        f.write('; Generated by mkmouth_a2.py -- do not edit.\n'
                '; The code unrolls on these, so they come before it.\n\n')
        for n, v in (('MOUTH_COL', MCOL), ('MOUTH_W', MW), ('MOUTH_ROW0', MROW),
                     ('MOUTH_H', MH), ('MOUTH_SIZE', MW * MH),
                     ('EYE_COL', ECOL), ('EYE_W', EW), ('EYE_ROW0', EROW),
                     ('EYE_H', EH), ('EYE_SIZE', EW * EH)):
            f.write('%-11s= %d\n' % (n, v))

    with open(os.path.join(SRCDIR, 'mouthdata_a2.inc'), 'w') as f:
        f.write('; Generated by mkmouth_a2.py -- do not edit.\n'
                '; The shapes as HGR bytes, composited over the face with OR,\n'
                '; so a change is a block copy and needs no rubbing out.\n\n')
        for label, group, names, geo in (
                ('mouth_bits', shapes, NAMES, (MCOL, MW, MROW, MH)),
                ('eye_bits', eyes, ENAMES, (ECOL, EW, EROW, EH))):
            f.write('%s:\n' % label)
            for i, nm in enumerate(names):
                data = hgr_bytes(group[i], *geo)
                f.write('        ; %d: %s\n' % (i, nm))
                for r in range(geo[3]):
                    f.write('        .byte ' + ','.join(
                        '$%02X' % v for v in data[r * geo[1]:(r + 1) * geo[1]]) + '\n')
            f.write('\n')
    print('wrote mouthdim_a2.inc and mouthdata_a2.inc')
