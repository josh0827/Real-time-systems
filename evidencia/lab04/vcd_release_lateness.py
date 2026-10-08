"""How late each sampling release is, against a fitted 1 ms grid.

Period jitter (max - min of consecutive periods) counts one late release twice.
This measures each instr_samp rise against a least-squares line through all of
them, which also removes the ~140 ppm offset between the C6 and analyzer
crystals, and then looks for a pattern in which releases are late.

Usage: python vcd_release_lateness.py capture.vcd [capture.vcd ...]
"""
import io
import sys
import statistics as st
from collections import Counter


def load(path):
    sym, ed, ts, now = {}, {}, None, 0
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        in_defs = True
        for line in fh:
            s = line.strip()
            if not s:
                continue
            if in_defs:
                if s.startswith("$timescale"):
                    p = s.split()
                    ts = float(p[1]) * {"ns": 1, "us": 1000}[p[2]]
                elif s.startswith("$var"):
                    p = s.split()
                    sym[p[3]] = p[4]
                    ed[p[4]] = []
                elif s.startswith("$enddefinitions"):
                    in_defs = False
                continue
            toks = s.split()
            if s.startswith("#"):
                now = int(toks[0][1:])
                toks = toks[1:]
            for t in toks:
                if t and t[0] in "01" and len(t) >= 2 and t[1:] in sym:
                    ed[sym[t[1:]]].append((now * ts, int(t[0])))
    return ed


for path in sys.argv[1:]:
    rises = [t for t, v in load(path)["D0"] if v]
    n = len(rises)
    mx, my = (n - 1) / 2, st.mean(rises)
    slope = sum((i - mx) * (y - my) for i, y in enumerate(rises)) / \
        sum((i - mx) ** 2 for i in range(n))
    dev = [(y - (my + slope * (i - mx))) / 1000 for i, y in enumerate(rises)]
    on_time = sorted(dev)[n // 100]          # 1st percentile = "released on time"
    late = sorted(d - on_time for d in dev)
    big = [i for i, d in enumerate(dev) if d - on_time > 4.0]
    print(path.split("/")[-1])
    print("  releases: %d   fitted period %.3f us" % (n, slope / 1000))
    print("  lateness vs grid: p50 %.2f   p99 %.2f   max %.2f us"
          % (late[n // 2], late[int(n * 0.99)], late[-1]))
    print("  releases more than 4 us late: %d (%.1f per second)"
          % (len(big), len(big) / ((rises[-1] - rises[0]) / 1e9)))
    for m in (5, 10, 50):
        print("    by release index mod %2d: %s" % (m, Counter(i % m for i in big).most_common(5)))
