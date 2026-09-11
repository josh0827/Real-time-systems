"""Three-regime analysis of the superloop sampling trace."""
import io
import sys
import statistics as st

PATH = sys.argv[1]
sym2name, edges, timescale_ns = {}, {}, None

with io.open(PATH, encoding="utf-8", errors="replace") as fh:
    in_defs = True
    for line in fh:
        line = line.strip()
        if not line:
            continue
        if in_defs:
            if line.startswith("$timescale"):
                p = line.split()
                timescale_ns = float(p[1])
                if p[2] == "us":
                    timescale_ns *= 1000
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
                    edges[nm].append((now * timescale_ns, int(t[0])))

us = lambda ns: ns / 1000.0
rises = {c: [t for t, v in e if v == 1] for c, e in edges.items()}
dur_s = max(max(v) for v in rises.values() if v) / 1e9

samp = rises["D0"]
per = [samp[i + 1] - samp[i] for i in range(len(samp) - 1)]

CATCHUP, BLOCKED = 500_000.0, 1_500_000.0   # ns
catch = [p for p in per if p < CATCHUP]
normal = [p for p in per if CATCHUP <= p <= BLOCKED]
blocked = [p for p in per if p > BLOCKED]

print("=" * 72)
print("Sampling trace, D0 = instr_samp, %.3f s, %d periods" % (dur_s, len(per)))
print("=" * 72)
print()
print("REGIME 1 - normal passes        : %5d  (%.2f %%)" % (len(normal), 100 * len(normal) / len(per)))
print("   min %8.2f  mean %8.2f  max %8.2f us   jitter %.2f us"
      % (us(min(normal)), us(st.mean(normal)), us(max(normal)), us(max(normal) - min(normal))))
print("   max deviation from 1000 us   : %.2f us" % us(max(abs(p - 1e6) for p in normal)))
print()
print("REGIME 2 - blocked by telemetry : %5d  (one every %.2f s)" % (len(blocked), dur_s / len(blocked)))
print("   min %8.2f  mean %8.2f  max %8.2f us"
      % (us(min(blocked)), us(st.mean(blocked)), us(max(blocked))))
print()
print("REGIME 3 - catch-up (backlog drain): %3d  (%.1f per blocked event)"
      % (len(catch), len(catch) / len(blocked)))
print("   min %8.2f  mean %8.2f  max %8.2f us"
      % (us(min(catch)), us(st.mean(catch)), us(max(catch))))
print()
print("ROW 1  mean sampling period over the whole capture : %.2f us" % us(st.mean(per)))
print("ROW 2  sampling jitter, max - min over %.0f s      : %.2f us" % (dur_s, us(max(per) - min(per))))
print("       worst single deviation from the 1000 us grid: %.2f us"
      % us(max(abs(p - 1e6) for p in per)))
print()

print("=" * 72)
print("CONTROL LOOP, D1 = instr_ctrl  (REQ-CTRL-01: period 10 ms, deadline = T)")
print("=" * 72)
ctrl = rises["D1"]
cper = [ctrl[i + 1] - ctrl[i] for i in range(len(ctrl) - 1)]
over = [p for p in cper if p > 10e6]
print("  periods: %d   min %.2f  mean %.2f  max %.2f us"
      % (len(cper), us(min(cper)), us(st.mean(cper)), us(max(cper))))
print("  periods longer than the 10 ms deadline: %d  (%.2f %%)"
      % (len(over), 100 * len(over) / len(cper)))
print("  worst overrun: %.2f us over deadline (%.0f %% of the period)"
      % (us(max(cper) - 10e6), 100 * (max(cper) - 10e6) / 10e6))
print()

print("=" * 72)
print("CPU UTILISATION with measured C_i")
print("=" * 72)


def width(ch):
    ev = edges[ch]
    r = [t for t, v in ev if v == 1]
    f = [t for t, v in ev if v == 0]
    w, fi = [], 0
    for x in r:
        while fi < len(f) and f[fi] <= x:
            fi += 1
        if fi < len(f):
            w.append(f[fi] - x)
    return st.mean(w) if w else 0.0


rows = [("sampling", "D0", 1e6), ("control", "D1", 10e6), ("telemetry", "D3", 1e9)]
U = 0.0
for name, ch, T in rows:
    c = width(ch)
    u = c / T
    U += u
    print("  %-10s C_i = %9.2f us   T = %9.1f ms   U = %6.3f %%"
          % (name, us(c), T / 1e6, 100 * u))
print("  %-10s %41s U = %6.3f %%" % ("TOTAL", "", 100 * U))
print()
print("  The CPU is idle %.2f %% of the time and the hard deadlines are still"
      % (100 * (1 - U)))
print("  missed. The problem is not load, it is the architecture.")
