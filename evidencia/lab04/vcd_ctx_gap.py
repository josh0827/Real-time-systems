"""Week 4 Task C: the visible cost of a context switch.

On every 10th sample the sampling thread gives control's semaphore and then
blocks on tick_q, so the gap between instr_samp (D0) falling and instr_ctrl (D1)
rising is one context switch plus the kernel calls around it (k_sem_give,
k_msgq_get). On the superloop the same gap is a plain function call, which makes
it the baseline: kernel gap minus superloop gap = what the switch adds.

Usage: python vcd_ctx_gap.py capture.vcd [console_poll_ms] [display_poll_ms]
The two sleeping threads wake without touching a pin, so their rates come from
the firmware (5 ms and 50 ms in firmware/kernel) instead of the trace.
"""
import io
import sys
import bisect
import statistics as st
from collections import Counter

PATH = sys.argv[1]
CONSOLE_POLL_MS = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
DISPLAY_POLL_MS = float(sys.argv[3]) if len(sys.argv) > 3 else 50.0

sym2name, edges, ts_ns, now = {}, {}, None, 0

with io.open(PATH, encoding="utf-8", errors="replace") as fh:
    in_defs = True
    for line in fh:
        line = line.strip()
        if not line:
            continue
        if in_defs:
            if line.startswith("$timescale"):
                p = line.split()
                ts_ns = float(p[1])
                if p[2] == "us":
                    ts_ns *= 1000
            elif line.startswith("$var"):
                p = line.split()
                sym2name[p[3]] = p[4]
                edges[p[4]] = []
            elif line.startswith("$enddefinitions"):
                in_defs = False
            continue
        toks = line.split()
        if line.startswith("#"):
            now = int(toks[0][1:])
            toks = toks[1:]
        for t in toks:
            if t and t[0] in "01" and len(t) >= 2:
                nm = sym2name.get(t[1:])
                if nm:
                    edges[nm].append((now * ts_ns, int(t[0])))

us = lambda ns: ns / 1000.0
rise = {c: [t for t, v in e if v == 1] for c, e in edges.items()}
fall = {c: [t for t, v in e if v == 0] for c, e in edges.items()}
dur = (max(max(v) for v in rise.values() if v) - min(min(v) for v in rise.values() if v)) / 1e9

# ---------------------------------------------------------------- the gap
samp_fall, ctrl_rise = fall["D0"], rise["D1"]
gaps = []
for r in ctrl_rise:
    k = bisect.bisect_right(samp_fall, r) - 1
    if k >= 0 and r - samp_fall[k] < 1e6:   # same release: under one period
        gaps.append(r - samp_fall[k])

print("=" * 74)
print("Task C - instr_samp falling (D0) -> instr_ctrl rising (D1), %.3f s" % dur)
print("=" * 74)
if not gaps:
    sys.exit("no D1 rise found within one period of a D0 fall")
gs = sorted(gaps)
p99 = gs[int(0.99 * (len(gs) - 1))]
print("  control releases matched : %d of %d" % (len(gaps), len(ctrl_rise)))
print("  gap  min %7.2f  mean %7.2f  p99 %7.2f  max %7.2f us"
      % (us(gs[0]), us(st.mean(gs)), us(p99), us(gs[-1])))
print("  most frequent values (us): " + ", ".join(
    "%.2f x%d" % (us(v), n) for v, n in Counter(gs).most_common(5)))
print("  (4 MHz capture: every value is a multiple of 0.25 us)")

# ---------------------------------------------------------------- overhead
rate = lambda ch: len(rise.get(ch, [])) / dur
wake = [
    ("sampling   (D0)", rate("D0")),
    ("control    (D1)", rate("D1")),
    ("telemetry  (D3)", rate("D3")),
    ("flow batch (D4)", rate("D4")),
    ("console    (%g ms sleep)" % CONSOLE_POLL_MS, 1000.0 / CONSOLE_POLL_MS),
    ("display    (%g ms sleep)" % DISPLAY_POLL_MS, 1000.0 / DISPLAY_POLL_MS),
]
total = sum(r for _, r in wake)
switches = 2 * total            # every wakeup is one switch in and one out
cost_us = switches * us(gs[-1])

print()
print("Overhead per second at this load (upper bound)")
print("-" * 74)
for name, r in wake:
    print("  %-26s %8.1f wakeups/s" % (name, r))
print("  %-26s %8.1f wakeups/s  -> x2 = %.0f switches/s" % ("total", total, switches))
print()
print("  %.0f switches/s x %.2f us (max gap) = %.0f us/s = %.2f %% of the CPU"
      % (switches, us(gs[-1]), cost_us, cost_us / 1e4))
print("  Upper bound: the gap also holds k_sem_give and k_msgq_get, and the")
print("  sampling -> control hand-off shares one switch instead of two.")
