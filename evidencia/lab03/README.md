# Week 3 evidence — the S3 port and the first thread

Status: **Task A done and build-verified. Tasks B and C are written and compiling,
but not yet measured: the ESP32-S3-DevKitC has not arrived.** Nothing in this
folder is a number taken from a board, and `ret.md` §3 keeps `____` in every S3
cell until it is.

## Contents

| File | What it is |
|---|---|
| `esp32s3_devkitc_esp32s3_procpu.overlay` | the port itself (Task A). Lives in the course repo at `firmware/superloop/boards/`; copied here because that repo is the professor's and we do not commit to it |
| `port-diffstat.txt` | what the port cost, plus the devicetree check that proves the overlay is picked up |
| `lab03-task-c.patch` | Task C (the sampling thread) as a patch against the week-2 superloop, so the two firmwares that feed columns 2 and 3 can be built from one tree |

## Task A — the port

86 lines, one file, **zero lines of C**. `src/main.c` is byte-identical to the
binary that produced the week-2 numbers on the L476, which is the whole claim
the session is asking us to back: changing silicon cost a hardware description,
not a port.

Pin map taken from `firmware/superloop/README.md`:

| Signal | S3 pin | Analyzer |
|---|---|---|
| `instr_samp` | GPIO4 | D0 |
| `instr_ctrl` | GPIO5 | D1 |
| `instr_cons` | GPIO6 | D2 |
| `instr_tele` | GPIO7 | D3 |
| `instr_flow` | GPIO15 | D4 |
| `instr_disp` | GPIO17 | D5 |
| `flow_pulse` (input) | GPIO16 | D6 |
| `valve_out` = `led0` | GPIO21 | (LED + jumper to GPIO16) |

Two things the guide does not mention and the overlay had to solve:

1. **There is no plain LED on this devkit.** Its only on-board LED is an
   addressable WS2812 on GPIO48, which a 50 Hz software PWM cannot drive. The
   valve is therefore an external LED on GPIO21, declared as `valve_out` and
   aliased to `led0`, which is what `main.c` looks for.
2. **`i2c0` is not on GPIO8/GPIO9 in Zephyr.** The firmware README documents the
   HMI on SDA GPIO8 / SCL GPIO9, but the board's own `i2c0_default` pinctrl
   (`boards/espressif/esp32s3_devkitc/esp32s3_devkitc-pinctrl.dtsi`) puts the bus
   on GPIO1/GPIO2, and GPIO2 is the ADC1 channel the pot fragment claims for
   pressure. Enabling `i2c0` alone would put the display and the pressure input
   on the same pin. The overlay declares its own `i2c0_hmi` pinctrl node to move
   the bus to the documented pair.

Build verification, both with and without the HMI, is in `port-diffstat.txt`.
The guide warns that the build also succeeds *without* the overlay and the
analyzer then shows flat lines, so the check that matters is the devicetree dump
at the end of that file: all eight nodes resolve to `&gpio0` at the right pins.

## Task C — the sampling thread

`lab03-task-c.patch` holds the four edits: `CONFIG_MAIN_THREAD_PRIORITY=10`,
the ISR posting release timestamps to a `k_msgq` instead of raising a counter,
the priority-2 `sampling_thread` blocking on that queue, and the loop reduced to
serving `control_pending`. It applies clean onto the week-2 tree and the result
compiles for the S3 with no warnings.

It is kept as a patch rather than applied in place so that one tree can build
both columns of the table in the right order:

```bash
cd ~/zephyrproject && source .venv/bin/activate
R=~/4101137-real-time-systems

# column 2 — S3 superloop (Task B)
west build -p -b esp32s3_devkitc/esp32s3/procpu $R/firmware/superloop && west flash

# column 3 — S3 + sampling thread (Task C)
cd $R && git apply ~/ret-equipo/evidencia/lab03/lab03-task-c.patch && cd -
west build -p -b esp32s3_devkitc/esp32s3/procpu $R/firmware/superloop && west flash
```

`backlog_peak` changes meaning between the two columns and the RET has to say so:
in the superloop it is an unbounded counter of ticks that piled up, and in the
thread build it is the occupancy of an 8-deep queue whose `k_msgq_put` is
`K_NO_WAIT`. A backlog of 8 in column 3 does not mean "8 ticks late", it means
releases were **dropped**, and the two numbers are not comparable without that
sentence.

## Measurement protocol (unchanged from week 2)

The week-2 reduction scripts in `../lab02/` read PulseView channel names, not
pins, so they work here as long as the ribbon keeps the order in the table above.

1. Flash, open the console on the devkit's **UART** jack (not the USB one),
   115200 8N1. Confirm `status` reports a moving `p=` before capturing.
2. PulseView, driver `fx2lafw`, 8 channels, **4 MHz**, 200 M samples = 49.999 s.
3. Three captures per column:
   - `baseline-50s-4MHz.vcd` — idle, no jumper.
   - `calib-flow-50s-4MHz.vcd` — jumper GPIO21 to GPIO16, `calib` issued at
     around t = 28 s.
   - console transcript with `status` before and after `calib`, for
     `backlog_peak` and, in column 3, `lat_peak_us`.
4. Export **VCD**, not CSV: 200 M samples are only around 110 k edges, so the
   file stays under 2 MB at full resolution.
5. Reduce with the week-2 scripts:
   ```bash
   python ../lab02/vcd_stats.py  baseline-50s-4MHz.vcd   > baseline-stats.txt
   python ../lab02/vcd_calib.py  calib-flow-50s-4MHz.vcd > calib-flow-stats.txt
   ```

The one wiring difference from week 2: the self-stimulus jumper runs from
**GPIO21 (valve) to GPIO16 (flow input)** instead of D13 to D9. The same caveat
carries over: the valve is written inside `task_sampling()`, so the pulse always
arrives at the same point of the cycle and the latency measured is the
deterministic case, not the worst case of an asynchronous sensor.
