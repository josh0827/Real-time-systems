"""Render a window of a sigrok VCD capture as a standalone SVG waveform figure.

    vcd_plot.py <capture.vcd> <out.svg> [title] [centre_s] [span_s]

With no centre, it frames the longest gap in the sampling channel, which is the
`calib` event. Whatever window is drawn, the longest sampling gap inside it is
highlighted and measured, so the figure states its own number.
"""
import io
import sys

VCD, OUT = sys.argv[1], sys.argv[2]
TITLE = sys.argv[3] if len(sys.argv) > 3 else None
CENTRE = float(sys.argv[4]) if len(sys.argv) > 4 else None
SPAN = float(sys.argv[5]) if len(sys.argv) > 5 else None

NAMES = [
    ("D0", "instr_samp", "sampling 1 kHz", "#1f5c8b"),
    ("D1", "instr_ctrl", "control 10 ms", "#2e7d4f"),
    ("D2", "instr_cons", "console", "#6b6b6b"),
    ("D3", "instr_tele", "telemetry 1 Hz", "#b3541e"),
    ("D4", "instr_flow", "flow batch", "#7a4fa3"),
    ("D5", "instr_disp", "display", "#8a8a8a"),
    ("D6", "flow_pulse", "flow input", "#a01b3f"),
]

sym, ed, ts = {}, {}, None
with io.open(VCD, encoding="utf-8", errors="replace") as fh:
    in_defs = True
    for line in fh:
        line = line.strip()
        if not line:
            continue
        if in_defs:
            if line.startswith("$timescale"):
                p = line.split()
                ts = float(p[1])
                if p[2] == "us":
                    ts *= 1000
            elif line.startswith("$var"):
                p = line.split()
                sym[p[3]] = p[4]
                ed[p[4]] = []
            elif line.startswith("$enddefinitions"):
                in_defs = False
            continue
        toks = line.split()
        if line.startswith("#"):
            now = int(toks[0][1:])
            toks = toks[1:]
        for t in toks:
            if t and t[0] in "01" and len(t) >= 2:
                nm = sym.get(t[1:])
                if nm:
                    ed[nm].append((now * ts, int(t[0])))


def pulses(ch):
    """(start_ns, end_ns) for every high interval."""
    out, start = [], None
    for t, v in ed.get(ch, []):
        if v == 1 and start is None:
            start = t
        elif v == 0 and start is not None:
            out.append((start, t))
            start = None
    return out


samp = pulses("D0")


def longest_gap(lo=None, hi=None):
    best, span = None, 0
    for i in range(len(samp) - 1):
        a, b = samp[i][1], samp[i + 1][0]
        if lo is not None and (b < lo or a > hi):
            continue
        if b - a > span:
            span, best = b - a, (a, b)
    return best, span


if CENTRE is None:
    (g0, g1), span = longest_gap()
    CENTRE = (g0 + g1) / 2 / 1e9
    SPAN = SPAN or span / 1e9 * 1.55

T0 = (CENTRE - SPAN / 2) * 1e9
T1 = (CENTRE + SPAN / 2) * 1e9
mark, gapspan = longest_gap(T0, T1)

ticks = int(gapspan / 1e6)  # floor: a 6.75 ms gap is 6 whole ticks queued, matching backlog_peak
if gapspan >= 1e6:
    gaplabel = "%.2f ms with no sampling at all = %d ticks" % (gapspan / 1e6, ticks)
else:
    gaplabel = "%.2f us" % (gapspan / 1e3)

if TITLE is None:
    TITLE = "The blocking command, measured"

W, LEFT, ROW, TOP = 1120, 170, 46, 104
H = TOP + ROW * len(NAMES) + 58
PW = W - LEFT - 30
x = lambda t: LEFT + (t - T0) / (T1 - T0) * PW

s = []
add = s.append
add('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" '
    'font-family="ui-monospace,Menlo,Consolas,monospace">' % (W, H, W))
add('<rect width="%d" height="%d" fill="#fbfaf8"/>' % (W, H))
add('<text x="%d" y="32" font-size="17" font-weight="700" fill="#1a1a1a">%s'
    '</text>' % (LEFT, TITLE))
add('<text x="%d" y="54" font-size="12.5" fill="#555">'
    'NUCLEO-L476RG superloop · rendered from %s · window %.0f ms at t = %.2f s'
    '</text>' % (LEFT, VCD.split("/")[-1], SPAN * 1000, CENTRE))

add('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#bbb"/>'
    % (LEFT, TOP - 16, LEFT + PW, TOP - 16))
for i in range(9):
    t = T0 + (T1 - T0) * i / 8
    px = x(t)
    add('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#bbb"/>'
        % (px, TOP - 21, px, TOP - 16))
    add('<text x="%.1f" y="%d" font-size="11" fill="#666" text-anchor="middle">'
        '%.0f ms</text>' % (px, TOP - 27, t / 1e6))

if mark:
    g0, g1 = mark
    add('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="#d92b2b" '
        'opacity="0.07"/>' % (x(g0), TOP - 10, x(g1) - x(g0), ROW * len(NAMES)))
    for gx in (g0, g1):
        add('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#d92b2b" '
            'stroke-width="1.4" stroke-dasharray="4 3"/>'
            % (x(gx), TOP - 10, x(gx), TOP + ROW * len(NAMES) - 14))
    mid, y = (x(g0) + x(g1)) / 2, TOP + ROW * len(NAMES) + 16
    add('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#d92b2b" '
        'stroke-width="1.4"/>' % (x(g0), y, x(g1), y))
    add('<text x="%.1f" y="%.1f" font-size="14" font-weight="700" '
        'fill="#d92b2b" text-anchor="middle">%s</text>' % (mid, y + 21, gaplabel))

for i, (ch, sig, what, colour) in enumerate(NAMES):
    top = TOP + i * ROW
    base, high = top + 26, top + 6
    add('<text x="12" y="%d" font-size="12.5" font-weight="700" fill="#1a1a1a">'
        '%s</text>' % (base, sig))
    add('<text x="12" y="%d" font-size="10.5" fill="#777">%s · %s</text>'
        % (base + 13, ch, what))
    add('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#ddd"/>'
        % (LEFT, base, LEFT + PW, base))
    n = 0
    for a, b in pulses(ch):
        if b < T0 or a > T1:
            continue
        px, pw = x(max(a, T0)), max(1.0, x(min(b, T1)) - x(max(a, T0)))
        add('<rect x="%.2f" y="%.1f" width="%.2f" height="%.1f" fill="%s"/>'
            % (px, high, pw, base - high, colour))
        n += 1
    if n == 0:
        add('<text x="%d" y="%.1f" font-size="11" fill="#aaa">flat</text>'
            % (LEFT + 8, base - 6))

add('</svg>')
io.open(OUT, "w", encoding="utf-8").write("\n".join(s))
print("wrote %s  (window %.1f ms at t=%.3f s, gap %s)"
      % (OUT, SPAN * 1000, CENTRE, gaplabel))
