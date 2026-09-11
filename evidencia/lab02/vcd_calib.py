"""Rows 3 and 5: flow-pulse service latency and sampling jitter under `calib`."""
import io
import sys
import statistics as st

PATH = sys.argv[1]
sym2name, edges, ts_ns = {}, {}, None

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
ms = lambda ns: ns / 1e6
rise = {c: [t for t, v in e if v == 1] for c, e in edges.items()}
fall = {c: [t for t, v in e if v == 0] for c, e in edges.items()}


def widths(ch):
    w, fi = [], 0
    for r in rise[ch]:
        while fi < len(fall[ch]) and fall[ch][fi] <= r:
            fi += 1
        if fi < len(fall[ch]):
            w.append(fall[ch][fi] - r)
    return w


dur = max(max(v) for v in rise.values() if v) / 1e9
print("=" * 74)
print("Capture: %.3f s   (D0 samp, D1 ctrl, D3 tele, D4 flow-batch, D6 flow-in)" % dur)
print("=" * 74)

# ---------------------------------------------------------------- row 3
print()
print("ROW 3 - flow pulse ISR -> loop service latency  (REQ-CTRL-05)")
print("-" * 74)
fin, fbatch = rise["D6"], rise["D4"]
print("  flow input pulses on D6 : %d  (%.1f Hz)" % (len(fin), len(fin) / dur))
print("  batch events on D4      : %d  (one per %.1f s)"
      % (len(fbatch), dur / max(len(fbatch), 1)))
print("  pulses per batch        : %.1f" % (len(fin) / max(len(fbatch), 1)))

lat = []
for tb in fbatch:
    prev = [t for t in fin if t <= tb]
    if prev:
        lat.append(tb - prev[-1])
if lat:
    print()
    print("  latency, 100th pulse -> instr_flow rising:")
    print("    min %8.2f us   mean %8.2f us   max %8.2f us"
          % (us(min(lat)), us(st.mean(lat)), us(max(lat))))
    print("    (the loop visits task_flow_batch once per pass, so this is")
    print("     bounded by one superloop cycle, not by the ISR)")

wf = widths("D4")
if wf:
    print()
    print("  C_i of task_flow_batch (D4 pulse width):")
    print("    min %8.2f us   mean %8.2f us   max %8.2f us"
          % (us(min(wf)), us(st.mean(wf)), us(max(wf))))

# ---------------------------------------------------------------- row 5
print()
print("ROW 5 - sampling jitter with `calib` running  (REQ-CTRL-08)")
print("-" * 74)
samp = rise["D0"]
per = [samp[i + 1] - samp[i] for i in range(len(samp) - 1)]
worst = max(per)
wi = per.index(worst)
print("  worst sampling period in the capture: %.2f ms  at t = %.3f s"
      % (ms(worst), samp[wi] / 1e9))
print("  ticks it spans: %d" % round(worst / 1e6))
print()
print("  row 2 baseline (no calib) was 6.77 ms; this is %.1fx worse."
      % (worst / 6765250.0))

big = sorted(per, reverse=True)[:6]
print("  six longest periods (ms): " + ", ".join("%.2f" % ms(p) for p in big))

after = [p for p in per[wi + 1: wi + 1 + 600] if p < 500000.0]
if after:
    print()
    print("  catch-up burst right after it: %d fast periods, mean %.2f us, total %.2f ms"
          % (len(after), us(st.mean(after)), ms(sum(after))))

tele = widths("D3")
if tele:
    print()
    print("  telemetry pulse width in this capture: mean %.2f us (n=%d)"
          % (us(st.mean(tele)), len(tele)))

# ---------------------------------------------------------------- control
print()
print("CONTROL LOOP under the same conditions  (REQ-CTRL-01)")
print("-" * 74)
c = rise["D1"]
cp = [c[i + 1] - c[i] for i in range(len(c) - 1)]
print("  min %.2f ms   mean %.2f ms   max %.2f ms"
      % (ms(min(cp)), ms(st.mean(cp)), ms(max(cp))))
print("  periods over the 10 ms deadline: %d of %d"
      % (len([p for p in cp if p > 10e6]), len(cp)))
