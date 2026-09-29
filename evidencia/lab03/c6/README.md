# Week 3 evidence — the C6 port and the first thread

This is the primary week-3 platform after the hardware requirement changed.
The C6 was already used for the week-1 bring-up, so this version uses the verified target
`esp32c6_devkitc/esp32c6/hpcore` and the RISC-V toolchain.

## Status

The port and thread are written, but the timing evidence is still pending.
Do not copy S3 numbers into this folder: sampling periods, latencies,
footprints and waveforms must be captured on the C6.

## Hardware port

[esp32c6_devkitc_esp32c6_hpcore.overlay](esp32c6_devkitc_esp32c6_hpcore.overlay)
defines the following map:

| Signal | C6 GPIO | Analyzer |
|---|---:|---|
| `instr_samp` | 3 | D0 |
| `instr_ctrl` | 4 | D1 |
| `instr_cons` | 5 | D2 |
| `instr_tele` | 6 | D3 |
| `instr_flow` | 7 | D4 |
| `instr_disp` | 10 | D5 |
| `flow_pulse` (input) | 11 | D6 |
| `valve_out` = `led0` | 2 | external LED + jumper to GPIO11 |

GPIO8 is deliberately unused because the C6 board's built-in indicator is an
addressable WS2812 on that pin. The valve output is therefore an external LED
on GPIO2, which was verified during the week-1 C6 bring-up. The HMI is not
enabled in this adaptation; its I2C pins must be selected from the actual board
pinctrl before adding a display.

## Builds

```bash
cd ~/zephyrproject && source .venv/bin/activate
R=~/4101137-real-time-systems

# column 2 — C6 superloop
west build -p -b esp32c6_devkitc/esp32c6/hpcore $R/firmware/superloop
west flash

# column 3 — C6 plus sampling thread
cd $R && git apply ~/ret-equipo/evidencia/lab03/c6/lab03-task-c.patch && cd -
west build -p -b esp32c6_devkitc/esp32c6/hpcore $R/firmware/superloop
west flash
```

The thread patch is platform-independent. Apply it only for column 3 and
reverse it before rebuilding column 2. The S3 folder is optional comparison
evidence, not a prerequisite for the C6 lab.

## Measurement protocol

Use the same PulseView setup as week 2: `fx2lafw`, 8 channels, 4 MHz and
200 M samples. Keep the analyzer channel order from the table above. For the
self-stimulus capture, jumper GPIO2 to GPIO11. Capture an idle baseline and a
`calib` run, then record `backlog_peak`; in the thread build also record
`lat_peak_us` and any dropped queue releases.

Reduce captures with the week-2 scripts:

```bash
python ../../lab02/vcd_stats.py baseline-50s-4MHz.vcd > baseline-stats.txt
python ../../lab02/vcd_calib.py calib-flow-50s-4MHz.vcd > calib-flow-stats.txt
```

The C6 is RISC-V while the S3 is Xtensa. Therefore the two platforms must be
reported as separate measurements, even when they run identical C code.
