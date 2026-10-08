# Week 4 evidence: the full migration and the A/B (ESP32-C6)

Status: **complete, measured on 2026-10-07.** Task A was built and checked
without the board (C6 build with 0 warnings, devicetree dump, `native_sim` run);
Tasks B, C and D, plus the missing week-3 cells, were measured in one session
with the C6 and the analyzer, following the plan below. Results are in `ret.md`
§3 week 4 and ADR-001.

## Contents

| File | What it is |
|---|---|
| `build-c6.txt` | C6 build of `firmware/kernel`: warnings, footprint against week 3, and the devicetree dump proving the overlay is applied |
| `native-sim-session.txt` | the node running on `native_sim`: telemetry every 1000 ms, `status`, `calib`, `threads` |
| `kernel-baseline-50s-4MHz.vcd` | capture 4: kernel at idle, jumper off |
| `kernel-calib-flow-50s-4MHz.vcd` | capture 5: kernel with the flow jumper and a `calib` at about 25 s |
| `console-kernel.txt`, `console-session.txt` | console logs of captures 4 and 5, each starting with the `kernel build` banner; the second ends with the `threads` output (Task D) |
| `kernel-baseline-stats.txt`, `kernel-calib-flow-jitter.txt`, `kernel-calib-flow-stats.txt` | `vcd_stats.py` and `vcd_calib.py` output for the A/B |
| `ctx-gap-baseline.txt`, `ctx-gap-calib.txt`, `ctx-gap-superloop.txt` | Task C, kernel at idle and under load, and the superloop's function-call baseline |
| `release-lateness.txt` | each release against a fitted 1 ms grid: where the kernel's extra idle jitter is |
| `fig-kernel-calib.svg`, `fig-kernel-ctx-gap.svg`, `fig-superloop-ctx-gap.svg` | figures rendered from the VCDs with `../lab02/vcd_plot.py` |
| `vcd_ctx_gap.py` | Task C reduction: `instr_samp` falling to `instr_ctrl` rising, plus the overhead-per-second bound |
| `vcd_release_lateness.py` | release lateness against a fitted grid, and which releases are late |
| `capture_console.py` | drives the console during a capture (`status`, `calib`, `threads` at fixed offsets) and logs it from the boot banner on |

The firmware is [`../../firmware/kernel/`](../../firmware/kernel/). The week-2
reduction scripts in `../lab02/` are reused as they are; `vcd_stats.py` now also
handles captures with no blocked regime (C6, kernel) and `vcd_calib.py` takes
the baseline to compare against as a second argument.

## The session: one sitting, three firmwares, five captures

It closes week 3 and week 4 together, because the A side of today's A/B is the
week-3 C6 superloop, whose `calib` capture is still missing.

### Builds

Superloop and sampling thread are the week-3 sources (course repo superloop +
`../lab02/lab02-tasks123.patch` + `../lab03/c6/lab03-task-c.patch`) with the C6
overlay from `../lab03/c6/`. The kernel is this repo's `firmware/kernel/`. Each
binary prints its own boot banner, which is how the console proves what is on
the board.

| Build dir (`~/zephyrproject/`) | Banner | FLASH / RAM |
|---|---|---|
| `build-lab03-c6-superloop` | `superloop build` | 133,556 / 51,088 B |
| `build-lab03-c6-thread` | `sampling-thread build` | 133,652 / 53,712 B |
| `build-lab04-c6-kernel` | `kernel build` | 134,132 / 67,552 B |

The superloop matches `../lab03/c6/footprint.txt` byte for byte. The thread
build is 16 B larger than the figure recorded there, consistent with that figure
predating `ticks_dropped`.

To rebuild on another machine (`R` = course repo with the week-2 patch applied):

```bash
L=~/zephyrproject/lab-apps; E=~/ret-equipo/evidencia
for v in superloop-c6 thread-c6; do
  cp -r $R/firmware/superloop $L/$v
  cp $E/lab03/c6/esp32c6_devkitc_esp32c6_hpcore.overlay $L/$v/boards/esp32c6_devkitc_hpcore.overlay
done
(cd $L/thread-c6 && git apply --recount -p3 $E/lab03/c6/lab03-task-c.patch)
west build -p -b esp32c6_devkitc/esp32c6/hpcore --build-dir build-lab03-c6-superloop $L/superloop-c6
west build -p -b esp32c6_devkitc/esp32c6/hpcore --build-dir build-lab03-c6-thread    $L/thread-c6
west build -p -b esp32c6_devkitc/esp32c6/hpcore --build-dir build-lab04-c6-kernel    ~/ret-equipo/firmware/kernel
```

`--recount` is needed because a hunk header in the C6 patch counts 41 added
lines where the hunk has 38; GNU `patch` and an out-of-repo `git apply` reject it
otherwise.

### Wiring

| Analyzer | Signal | C6 GPIO |
|---|---|---|
| D0 | `instr_samp` | 3 |
| D1 | `instr_ctrl` | 4 |
| D2 | `instr_cons` | 5 |
| D3 | `instr_tele` | 6 |
| D4 | `instr_flow` | 7 |
| D5 | `instr_disp` | 10 |
| D6 | `flow_pulse` (input) | 11 |
| GND | GND | GND |

Self-stimulus jumper for the `calib`/flow captures: **GPIO2 (valve) to GPIO11**.
Before starting a flow capture, check that D6 shows the 50 Hz valve PWM and that
`status` reports `batches` going up. The earlier attempt
(`../lab03/c6/thread-calib-flow-attempt-50s-4MHz.vcd`) had only 43 edges on D6
in 50 s, which looks like a jumper without contact.

Console on the CH343 UART port (not the native USB one), attached to WSL with
`conectar-esp32.cmd`, at `/dev/ttyACM0`, 115200 8N1. Log it while typing,
from inside the Zephyr venv (it brings pyserial):

```bash
script -q -c "python -m serial.tools.miniterm /dev/ttyACM0 115200" console-<name>.txt
```

(`west espressif monitor` does not accept `--build-dir`, so it cannot follow
these named build directories.)

### Captures

PulseView, `fx2lafw`, 8 channels, **4 MHz, 200 M samples (49.999 s)**, export
**VCD**. For every `calib` capture: start the analyzer, `status` at about 5 s,
`calib` at about 28 s, `status` again after `calibration done`.

| # | Flash | Jumper | Capture | Saves |
|---|---|---|---|---|
| 1 | `build-lab03-c6-superloop` | on | `calib` | `../lab03/c6/superloop-calib-flow-50s-4MHz.vcd` + console |
| 2 | `build-lab03-c6-thread` | off | baseline | `../lab03/c6/thread-baseline-v2-50s-4MHz.vcd` + console with the banner |
| 3 | `build-lab03-c6-thread` | on | `calib` | `../lab03/c6/thread-calib-flow-50s-4MHz.vcd` + console |
| 4 | `build-lab04-c6-kernel` | off | baseline | `kernel-baseline-50s-4MHz.vcd` |
| 5 | `build-lab04-c6-kernel` | on | `calib`, then `threads` | `kernel-calib-flow-50s-4MHz.vcd` + `console-session.txt` |

`west flash --build-dir <dir>` between captures. After flashing, the first thing
in each console log must be the banner of the table above.

### Reductions

```bash
cd ~/ret-equipo/evidencia
python3 -I lab02/vcd_stats.py lab04/kernel-baseline-50s-4MHz.vcd   > lab04/kernel-baseline-stats.txt
python3 -I lab02/vcd_calib.py lab04/kernel-calib-flow-50s-4MHz.vcd 1112.75 > lab04/kernel-calib-flow-stats.txt
python3 -I lab04/vcd_ctx_gap.py lab04/kernel-baseline-50s-4MHz.vcd  > lab04/ctx-gap-baseline.txt
python3 -I lab04/vcd_ctx_gap.py lab04/kernel-calib-flow-50s-4MHz.vcd > lab04/ctx-gap-calib.txt
# same two week-2 scripts for captures 1 to 3, into ../lab03/c6/*-stats.txt
```

`1112.75` is the C6 superloop's worst baseline period, the comparison point for
`vcd_calib.py`. Then fill the `____` cells in `ret.md` §3 (weeks 3 and 4) and in
ADR-001 (§2).
