# Week 2 evidence — superloop baseline (NUCLEO-L476RG)

Every number in [`../../ret.md`](../../ret.md) §3 is recomputed from the files in
this folder. Nothing here is transcribed by hand.

## Contents

### Raw captures

| File | Conditions | Feeds |
|---|---|---|
| `baseline-50s-4MHz.vcd` | node idle, no flow stimulus, cache on | rows 1, 2, all `C_i` |
| `calib-flow-50s-4MHz.vcd` | jumper D13→D9, `calib` issued at t ≈ 27.8 s | rows 3, 5, the ISR cost |
| `nocache-50s-4MHz.vcd` | `nocache.conf`, jumper removed | row 4 |
| `console-session.txt` | console transcript, `status` / `calib` / `status` | row 6 |

All three captures: PulseView with `fx2lafw`, 8 channels, **4 MHz** (250 ns
resolution), 200 M samples = **49.999 s**.

VCD rather than CSV because it records only transitions: 200 M samples reduce to
~110 k edges, so a 1.7 MB file keeps every edge at full resolution, and a CSV of
the same capture would be several gigabytes.

### Reduction scripts

Run any of them to reproduce the tables in the RET.

| Script | Produces |
|---|---|
| `vcd_stats.py <vcd>` | three-regime split of the sampling grid, `C_i`, utilisation |
| `vcd_calib.py <vcd>` | flow-pulse latency, the `calib` excursion |
| `vcd_isr_cost.py <vcd>` | control periods classified by flow-ISR presence |
| `vcd_cache_compare.py <on.vcd> <off.vcd>` | cache on versus cache off |
| `vcd_plot.py <vcd> <out.svg> [title] [centre_s] [span_s]` | a waveform figure of any window, with the longest sampling gap inside it measured and labelled |

Their saved output: `baseline-stats.txt`, `calib-flow-stats.txt`,
`isr-cost-stats.txt`, `cache-comparison.txt`.

### Figures

Generated from the committed captures, so they can be regenerated rather than
trusted. With no centre argument `vcd_plot.py` frames the longest sampling gap
in the file, which is the `calib` event.

| File | What it shows |
|---|---|
| `fig-telemetry-blocks-sampling.svg` | Idle baseline, 40 ms window. The 1 kHz train on D0 stops for the width of the telemetry pulse on D3: 6.75 ms, 6 whole ticks queued, which is the `backlog_peak` the firmware reported. |
| `fig-calib-416ms.svg` | Task C, 645 ms window. 416.10 ms with no sampling at all. `instr_cons` on D2 stays high across the whole window, so the console task is visibly the one holding the loop; `flow_pulse` on D6 stops pulsing because the valve PWM that drives it lives inside `task_sampling()`; and D1 is silent, so REQ-CTRL-01 and REQ-CTRL-02 fail together. |
| `fig-nocache-telemetry.svg` | Cache off, same 40 ms view as the baseline figure. The blocking is unchanged (6.98 ms) because it is UART-bound. |

The tick count on each figure is the floor of the gap in milliseconds, not the
rounded value: a 6.75 ms gap is 6 whole ticks queued, which is what
`backlog_peak` counts.

### Screenshots

| File | What it shows |
|---|---|
| `shot-01-recon-telemetry-blocks-sampling.png` | Reconnaissance capture, 2.5 s. First sight of the effect: the wide pulse on D3 (telemetry) and the gap in the D0 train (sampling) start and end together. |
| `shot-02-baseline-telemetry-blocks-sampling.png` | The same in the 50 s baseline, at t ≈ 22.55 s. This is the 5980 µs of polled-UART blocking that makes the idle `backlog_peak` 6. |
| `shot-03-flow-50hz-and-telemetry.png` | With the jumper installed: D6 carries the 50 Hz flow stimulus and the telemetry gap is still there. The capture behind rows 3 and 5. |
| `shot-04-nocache-wide-view.png` | Cache-off capture, ~1.3 s across the screen, D6 flat again (jumper removed so the conditions match the baseline). |
| `shot-05-nocache-telemetry.png` | Cache-off, telemetry pulse. The blocking is unchanged because it is UART-bound, while `C_i` of the compute tasks grew 47–86 %. |
| `shot-06-calib-capture-overview.png` | The `calib` capture reopened in PulseView, first second of the file. Useful as an overview of the whole signal set at once: the 50 Hz flow stimulus on D6, a telemetry pulse on D3 with its gap in D0, and a flow batch pulse on D4. The `calib` event itself is at t ≈ 27.8 s, outside this window; see `fig-calib-416ms.svg`. |

### Task A

| File | |
|---|---|
| `flow-diagram.md` | the ten-box flow, as a Mermaid graph GitHub renders |
| `lab02-tasks123.patch` | the three pieces we completed in `main.c` |

## Reproducing the measurements

### Wiring

Six instrumentation pins on the unbroken Arduino run **D3 to D8**, flow input on
**D9**. D3–D7 sit on CN9 and D8–D9 on CN5, collinear on the same board edge.
Ground from CN6.

| Analyzer | PulseView | Arduino | Port | Signal |
|---|---|---|---|---|
| CH1 | D0 | D3 | PB3 | `instr_samp` |
| CH2 | D1 | D4 | PB5 | `instr_ctrl` |
| CH3 | D2 | D5 | PB4 | `instr_cons` |
| CH4 | D3 | D6 | PB10 | `instr_tele` |
| CH5 | D4 | D7 | PA8 | `instr_flow` |
| CH6 | D5 | D8 | PA9 | `instr_disp` |
| CH7 | D6 | D9 | PC7 | `flow_pulse` (input) |
| GND | | GND | | common ground, mandatory |

Three numbering schemes for seven wires. Confirm the map from the signals, not
the labels: sampling is a dense 1 kHz train, control is one pulse per ten of
them, telemetry is one wide pulse per second, and anything not stimulated is
flat.

### Build and flash

```bash
source ~/zephyrproject/.venv/bin/activate
cd ~/zephyrproject
west build -p -b nucleo_l476rg ~/4101137-real-time-systems/firmware/superloop
```

Expected: FLASH 25 492 B of 1 MB (2.43 %), RAM 3 840 B of 96 KB (3.91 %).

No flashing tool is installed in this WSL setup and none is needed. The ST-LINK
exposes a mass storage volume:

```powershell
Copy-Item \\wsl.localhost\Ubuntu-24.04\home\joshua\zephyrproject\build\zephyr\zephyr.bin E:\
```

The file disappearing from the volume is the success signal; a `FAIL.TXT`
appearing is the error report. Console on the ST-LINK VCP at 115200 8N1.

### Flow stimulus without extra hardware

A jumper from **D13 (PA5, the valve output) to D9 (PC7, the flow input)** makes
the node's own valve drive its own flow sensor. The valve runs a software PWM at
1 kHz / 20 = 50 Hz, giving 50 pulses per second and a flow batch every 2 s.

Its limitation is recorded in the RET and matters: the valve is written inside
`task_sampling()`, so every edge arrives at the same point of the loop cycle.
The resulting latency is deterministic (25 ns of spread over 25 events) and is
**not** the worst case a free-running sensor would produce.

### Cache-off run

```bash
west build -p -b nucleo_l476rg ~/4101137-real-time-systems/firmware/superloop \
  -- -DEXTRA_CONF_FILE=nocache.conf
```

Remove the jumper first: row 4 is compared against row 2, which was measured
without a flow stimulus, and only one variable may change at a time.

Verify the fragment actually took effect before trusting the capture:

```bash
grep -E "LAB_FLASH_CACHE_OFF|STM32_FLASH_PREFETCH" build/zephyr/.config
find build -name "cache_stm32l4*"
```

Expected `CONFIG_LAB_FLASH_CACHE_OFF=y`, prefetch unset, and
`cache_stm32l4.c.obj` present.

> **For any pair measuring on an STM32C0116-DK instead:** this fragment is a
> silent no-op there. `CONFIG_LAB_FLASH_CACHE_OFF` declares
> `depends on SOC_SERIES_STM32L4X`, so Kconfig drops it without a warning on a C0
> and `cache_stm32l4.c` is never compiled. The C0 has no ART accelerator. Only
> `CONFIG_STM32_FLASH_PREFETCH=n` applies, so their row 4 measures the flash
> prefetch buffer, and reporting it as a cache measurement would be reporting a
> cache that was never enabled.

## Results

| # | Measurement | Value |
|---|---|---|
| 1 | Mean sampling period | **999.02 µs** |
| 2 | Sampling jitter, max over 50 s | **6753.25 µs** (10.75 µs clean regime) |
| 3 | Flow ISR to loop service | **9.67 µs** (deterministic stimulus) |
| 4 | Sampling jitter, cache off | **119.25 µs** clean regime, 11× row 2 |
| 5 | Sampling jitter during `calib` | **416.11 ms** |
| 6 | `backlog_peak`, idle → `calib` | **6 → 416 ticks** |

`C_i`: sampling 4.95 µs, control 1.35 µs, telemetry 5980.36 µs, flow batch
70.62 µs, flow ISR 11.50 µs. **Total utilisation 1.169 %.**

The analysis is in `../../ret.md` §3. The short version: the processor is idle
98.83 % of the time and three hard requirements are violated once per second
anyway, so the failure is architectural rather than a shortage of cycles.
