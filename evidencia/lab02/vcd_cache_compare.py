"""Row 4: what the ART accelerator was doing for us.

Same source, same pins, same clock. The only difference between the two
captures is CONFIG_LAB_FLASH_CACHE_OFF + CONFIG_STM32_FLASH_PREFETCH=n.
"""
import io
import sys
import statistics as st


def load(path):
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
    return ed


us = lambda ns: ns / 1000.0


def stats(ed):
    out = {}
    for ch in ("D0", "D1", "D3"):
        r = [t for t, v in ed[ch] if v == 1]
        f = [t for t, v in ed[ch] if v == 0]
        w, fi = [], 0
        for x in r:
            while fi < len(f) and f[fi] <= x:
                fi += 1
            if fi < len(f):
                w.append(f[fi] - x)
        per = [r[i + 1] - r[i] for i in range(len(r) - 1)]
        out[ch] = (w, per)
    return out


a = stats(load(sys.argv[1]))   # cache on
b = stats(load(sys.argv[2]))   # cache off

print("=" * 76)
print("ROW 4 - flash cache ON vs OFF, identical binary source")
print("=" * 76)
print()
print("  C_i, mean instrumentation pulse width")
print("  %-26s %12s %12s %10s" % ("task", "cache ON", "cache OFF", "penalty"))
print("  " + "-" * 62)
for ch, name in (("D0", "task_sampling"), ("D1", "task_control"),
                 ("D3", "task_telemetry")):
    ma, mb = st.mean(a[ch][0]), st.mean(b[ch][0])
    print("  %-26s %9.2f us %9.2f us %+8.1f %%"
          % (name, us(ma), us(mb), 100 * (mb - ma) / ma))

print()
print("  Sampling period, normal regime only (500 us to 1500 us)")
na = [p for p in a["D0"][1] if 500e3 <= p <= 1.5e6]
nb = [p for p in b["D0"][1] if 500e3 <= p <= 1.5e6]
for label, v in (("cache ON ", na), ("cache OFF", nb)):
    print("    %s  n=%d  min %.2f  mean %.2f  max %.2f  jitter %.2f us"
          % (label, len(v), us(min(v)), us(st.mean(v)), us(max(v)),
             us(max(v) - min(v))))

print()
print("  Telemetry blocking, the I/O-bound part")
ba = [p for p in a["D0"][1] if p > 1.5e6]
bb = [p for p in b["D0"][1] if p > 1.5e6]
print("    cache ON   n=%d  mean %.2f ms" % (len(ba), st.mean(ba) / 1e6))
print("    cache OFF  n=%d  mean %.2f ms" % (len(bb), st.mean(bb) / 1e6))
print("    change: %+.2f %%" % (100 * (st.mean(bb) - st.mean(ba)) / st.mean(ba)))

print()
print("=" * 76)
print("  ROW 4 answer: sampling jitter, max, cache off")
allp = b["D0"][1]
print("    over the whole capture : %.2f us" % us(max(allp) - min(allp)))
print("    normal regime only     : %.2f us" % us(max(nb) - min(nb)))
print("    row 2 was 6753.25 us / 10.75 us in the normal regime")
print("=" * 76)
