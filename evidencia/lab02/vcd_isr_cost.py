"""Does the flow ISR explain the extra control-loop deadline misses?

For every control period, count how many flow-input rising edges fall inside it,
then compare the period length across those groups. Same capture, same board,
so everything else is held constant.
"""
import io
import sys
import bisect
import statistics as st

path = sys.argv[1]
sym, ed, ts = {}, {}, None
with io.open(path, encoding="utf-8", errors="replace") as fh:
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

us = lambda ns: ns / 1000.0
r = lambda c: [t for t, v in ed[c] if v == 1]
ctrl, flow, tele, batch = r("D1"), r("D6"), r("D3"), r("D4")

groups = {}
for i in range(len(ctrl) - 1):
    a, b = ctrl[i], ctrl[i + 1]
    p = b - a
    if not (5e6 <= p <= 20e6):          # drop calib and catch-up outliers
        continue
    if any(a <= t <= b for t in tele):  # drop the telemetry-blocked ones
        continue
    if any(a <= t <= b for t in batch):  # drop the flow-batch ones
        continue
    n = bisect.bisect_right(flow, b) - bisect.bisect_left(flow, a)
    groups.setdefault(n, []).append(p)

print("=" * 72)
print("Control periods classified by how many flow ISRs fired inside them")
print("(telemetry and flow-batch periods excluded, so the ISR is the only")
print(" difference left between the groups)")
print("=" * 72)
print()
print("  flow ISRs |  count |     mean |      min |      max | over 10 ms")
print("  ----------|--------|----------|----------|----------|-----------")
base = None
for n in sorted(groups):
    v = groups[n]
    if len(v) < 20:
        continue
    over = len([p for p in v if p > 10e6])
    print("      %d     | %6d | %8.2f | %8.2f | %8.2f | %5d (%5.1f %%)"
          % (n, len(v), us(st.mean(v)), us(min(v)), us(max(v)), over,
             100 * over / len(v)))
    if n == 0:
        base = st.mean(v)

if base is not None:
    print()
    for n in sorted(groups):
        if n > 0 and len(groups[n]) >= 20:
            d = st.mean(groups[n]) - base
            print("  cost of %d flow ISR(s): %+.2f us   -> %.2f us per interrupt"
                  % (n, us(d), us(d) / n))
    print()
    print("  margin of the control loop against its 10 ms deadline")
    print("  with no flow input at all: %.2f us  (%.4f %% of the period)"
          % (us(10e6 - base), 100 * (10e6 - base) / 10e6))
