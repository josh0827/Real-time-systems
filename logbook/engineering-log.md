# Engineering Logbook

Running record of what we did and how we did it. One entry per lab session,
newest at the bottom.

This is **not** the RET. The RET holds timing requirements and measured
evidence, and it is what gets graded. This logbook holds the working detail:
setup steps, dead ends, error messages and the reasoning behind our choices,
so that any of us can reproduce a result months later without deriving it
again from scratch.

<details>
<summary><b>How to write an entry</b></summary>

Each entry keeps the same shape. Goal, Result and Open items stay visible so
the file can be scanned; the long sections are collapsed.

| Field | Meaning | Collapsed |
|---|---|---|
| Goal | What the session was supposed to achieve | no |
| Setup | Hardware and toolchain actually used | yes |
| What we did | The steps that worked, as commands | yes |
| Problems | What broke, the real cause, and the fix | yes, one block per problem |
| Result | What we can demonstrate at the end | no |
| Open items | What is still missing | no |

Collapsible blocks are plain HTML, which GitHub renders as an accordion:

```markdown
<details>
<summary>Title</summary>

Content.

</details>
```

The blank line after `</summary>` is mandatory. Without it the markdown inside
is rendered as literal text.

</details>

---

## Entry 01: Week 1 bring-up

**Date:** 2026-09-03 · **Lab:** `labs/lab01_bringup.md` · **Author:** Joshua
· **Board:** ESP32-C6-DevKitC

### Goal

Get a working build, flash and monitor cycle on a physical board and on
`native_sim`, and create the team RET from the course template. No timing
measurements this week: the deliverable is the environment itself.

<details>
<summary><b>Setup</b></summary>

| Item | Value |
|---|---|
| Host | Windows 11 + WSL2, Ubuntu-24.04 |
| RTOS | Zephyr 4.4.0, west 1.5.0, Zephyr SDK 1.0.1 |
| Board | ESP32-C6-DevKitC |
| Board target | `esp32c6_devkitc/esp32c6/hpcore` |
| Architecture | RISC-V, toolchain `riscv64-zephyr-elf` |
| Serial bridge | CH343 (`1a86:55d3`), enumerates as `/dev/ttyACM0` |
| Console | 115200 8N1 |

**Deviation from the lab specification.** The lab asks for the STM32C0116-DK,
a Cortex-M0+ that the course lends out for weeks 1 and 2 and that serves as a
clean cacheless baseline. We did not have it available, so this session ran on
the ESP32-C6 we already own. The build, flash and monitor workflow is identical
except for the board target; only the LED sample had to change, for the reason
described below. The C0116-DK run is still pending.

</details>

<details>
<summary><b>What we did</b></summary>

Every command runs from inside the west workspace, with the virtualenv active:

```bash
source ~/zephyrproject/.venv/bin/activate
cd ~/zephyrproject
```

**1. Expose the board to WSL.** WSL does not see USB devices by default. The
`usbipd-win` tool forwards them from Windows:

```powershell
usbipd bind --busid 2-1       # once, needs administrator
usbipd attach --wsl --busid 2-1
```

**2. Blink an LED.**

```bash
west build -p always -b esp32c6_devkitc/esp32c6/hpcore \
  zephyr/samples/drivers/led/led_strip \
  -- -DCONFIG_SAMPLE_LED_UPDATE_DELAY=500 -DCONFIG_SAMPLE_LED_BRIGHTNESS=64
west flash
```

**3. Serial console.**

```bash
west build -p always -b esp32c6_devkitc/esp32c6/hpcore zephyr/samples/hello_world
west flash
west espressif monitor -p /dev/ttyACM0     # exit with Ctrl+]
```

**4. Close the iteration cycle.** We copied `hello_world` out of the Zephyr
tree so the source stays ours, edited the `printf`, and rebuilt without
`-p always` so only the changed file recompiles.

**5. Native simulator.**

```bash
west build -p always -b native_sim ~/lab01/hello_lab01 --build-dir /tmp/nsim
timeout 5 /tmp/nsim/zephyr/zephyr.exe
```

</details>

<details>
<summary><b>Problems</b> (4)</summary>

<details>
<summary><code>samples/basic/blinky</code> does not build for this board</summary>

```
main.c:15:19: error: '__device_dts_ord_DT_N_ALIAS_led0...' undeclared
#define LED0_NODE DT_ALIAS(led0)
```

The cause is in the devicetree, not in the sample. `esp32c6_devkitc` declares
only two aliases, `sw0` and `watchdog0`. There is no `led0` because the board
has no plain GPIO LED: its only onboard LED is an addressable WS2812 on GPIO8.

Two ways out, both verified to compile:

1. Supply our own overlay defining `led0` over an external LED, which keeps the
   canonical blinky sample:

   ```dts
   #include <zephyr/dt-bindings/gpio/gpio.h>

   / {
       leds {
           compatible = "gpio-leds";
           led_ext: led_ext {
               gpios = <&gpio0 2 GPIO_ACTIVE_HIGH>;
           };
       };
       aliases { led0 = &led_ext; };
   };
   ```

2. Use `samples/drivers/led/led_strip`, which already ships an official
   `esp32c6_devkitc_hpcore.overlay`.

We took option 2 because it needs no extra hardware. Worth noting for later:
that overlay drives the WS2812 over **I2S with DMA**, not bit-banging. The
WS2812 protocol demands pulse widths accurate to hundreds of nanoseconds, which
no RTOS thread can guarantee, so the timing is delegated to a peripheral. This
is exactly the kind of decision the RET will later have to justify with numbers.

The sample defaults are unusable as evidence: with `chain-length = 1` and a
50 ms delay the LED cycles too fast to read, and brightness 16 of 255 barely
registers on camera. We raised them to 500 ms and 64.

</details>

<details>
<summary><code>west espressif monitor</code> fails with "could not find build configuration"</summary>

The command does not accept `--build-dir`. Its implementation calls
`find_build_dir(None, True)` with the argument hardcoded, so it only works when
west can guess the build directory on its own. We had set
`build.dir-fmt = ~/lab01/{app}`, and with three directories matching that
wildcard the guess became ambiguous and failed, even for `--help`.

Fix: drop the custom `build.dir-fmt` and keep builds in the default
`~/zephyrproject/build`. Then `flash` and `monitor` both work with no flags.

</details>

<details>
<summary><code>bind</code> persists, <code>attach</code> does not</summary>

`usbipd bind` writes a flag to the Windows registry and survives reboots.
`usbipd attach` opens a live TCP connection carrying the USB/IP protocol to the
`vhci-hcd` driver in the WSL kernel, so it dies when the board is unplugged,
when WSL shuts down, or on reboot. Running `usbipd attach --wsl --auto-attach`
in a window left open reconnects automatically.

Use the **CH343** UART bridge, not the ESP32 native USB (`303a:1001`). The
native interface disappears from the bus every time the chip resets, and the
chip resets in the middle of flashing, which drops the attach halfway through.

</details>

<details>
<summary>The <code>native_sim</code> binary never exits</summary>

It sits in the RTOS idle loop, so any script has to wrap it in `timeout`.

</details>

</details>

### Result

| Check | Status |
|---|---|
| LED blinking on the board | Done, `evidencia/lab01/led.mp4` |
| `hello_world` on hardware, serial console | Done, `evidencia/lab01/hello-world.jpeg` |
| Modified message, full rebuild cycle | Done, `evidencia/lab01/mensaje-propio.jpeg` |
| `hello_world` on `native_sim` | Done, `evidencia/lab01/native-sim.png` |
| Team RET under version control | Done, this repository |

### Open items

- Repeat the LED and console steps on the STM32C0116-DK once the course lends
  it out, and record that run here.
- Add the second team member to the RET header and as a repository
  collaborator.
- The ESP32-S3 is needed from week 3 on. The C6 is not a substitute: it changes
  architecture and toolchain, and it breaks the week 9 AMP lab.
- The 8-channel logic analyzer is needed by week 2. It is the instrument every
  later timing measurement depends on.

---

## Entry 02: Week 2 superloop, run and read

**Date:** 2026-09-10 · **Lab:** `labs/lab02_superloop.md` · **Author:** Joshua
· **Board:** NUCLEO-L476RG · **Team:** Joshua, David Henao Rojas, Ismael Cortés Ramírez

### Goal

Complete the three marked pieces of the provided superloop, run it on hardware,
and fill every row of the week-2 evidence table with measured numbers: the flow
diagram, the EARS requirements in RET §1, and the latency and jitter table in
RET §3.

<details>
<summary><b>Setup</b></summary>

| Item | Value |
|---|---|
| Host | Windows 11 + WSL2, Ubuntu-24.04 |
| RTOS | Zephyr 4.4.0 (tree at v4.4.0-13771-gb9df9f46ae46), west 1.5.0, SDK 1.0.1 |
| Board | NUCLEO-L476RG (STM32L476RG, Cortex-M4F at 80 MHz) |
| Board target | `nucleo_l476rg` (`nucleo_l476rg/stm32l476xx`) |
| Architecture | ARM Cortex-M4F, toolchain `arm-zephyr-eabi` 14.3.0 |
| Debug probe | ST-LINK/V2-1, firmware V2J46M31, mass storage volume `NODE_L476RG` |
| Console | ST-LINK VCP (usart2), 115200 8N1, COM16 on this host |
| Footprint | FLASH 25 492 B / 1 MB (2.43 %), RAM 3 840 B / 96 KB (3.91 %) |
| Analyzer | Saleae Logic clone, `0925:3881`, Cypress FX2, 8 ch |
| Analyzer software | PulseView (sigrok), driver `fx2lafw` over WinUSB |
| Capture settings | 8 channels, 4 MHz (250 ns resolution), 200 M samples = 49.999 s |

The team is now three: David Henao Rojas and Ismael Cortés Ramírez joined, which
closes the open item carried from entry 01.

</details>

<details>
<summary><b>What we did</b></summary>

**1. The three missing pieces**, all in `firmware/superloop/src/main.c`. The
diff is kept as `evidencia/lab02/lab02-tasks123.patch`.

- `instr_set()` (line 74): the GPIO toggle behind every instrumentation pin.
  Without it the analyzer sees six flat lines.
- `tick_isr()` (line 88): the 1 kHz timer ISR does not sample. It increments
  `ticks_pending` and keeps the worst pile-up in `backlog_peak`.
- `main()` (line 497): the `while (1)` itself, visiting the six tasks in a fixed
  order and draining exactly one pending tick per pass.

Before writing the loop, the build states its own job description: the six task
functions all warn as *defined but not used*, because the one thing whose job is
to call them is what is missing.

**2. Build and flash.**

```bash
source ~/zephyrproject/.venv/bin/activate
cd ~/zephyrproject
west build -p -b nucleo_l476rg ~/4101137-real-time-systems/firmware/superloop
```

```powershell
Copy-Item \\wsl.localhost\Ubuntu-24.04\home\joshua\zephyrproject\build\zephyr\zephyr.bin E:\
```

**3. Three captures, each isolating one variable.**

| Capture | File | What it adds |
|---|---|---|
| Baseline, node idle | `baseline-50s-4MHz.vcd` | rows 1 and 2, all `C_i` |
| Jumper D13→D9 plus `calib` | `calib-flow-50s-4MHz.vcd` | rows 3 and 5, the ISR cost |
| `nocache.conf`, jumper removed | `nocache-50s-4MHz.vcd` | row 4 |

Row 6 came from the console (`status` before and after `calib`).

**4. Reduction.** VCD was chosen over CSV because it records only transitions:
50 s at 4 MHz is 200 M samples but only ~110 k edges, so a 1.7 MB file holds
every edge at full resolution. The scripts in `evidencia/lab02/` recompute every
number in the RET from those files, so a claim can be re-derived rather than
trusted:

| Script | Produces |
|---|---|
| `vcd_stats.py` | three-regime split, `C_i`, utilisation |
| `vcd_calib.py` | flow latency, `calib` excursion |
| `vcd_isr_cost.py` | the controlled ISR comparison |
| `vcd_cache_compare.py` | cache on vs off |

**5. A stimulus for D9 without buying anything.** Row 3 needs flow pulses. A
jumper from **D13 (PA5, the valve output) to D9 (PC7, the flow input)** makes the
node's own valve drive its own flow sensor. The valve runs a software PWM at
1 kHz / 20 = 50 Hz, which gives 50 pulses per second and a flow batch every 2 s.
It is also physically coherent: flow exists because the valve is open. The
limitation is recorded in the RET, since a self-generated stimulus is
phase-locked to the loop and a real sensor would not be.

</details>

<details>
<summary><b>Channel map, verified by signature</b></summary>

Three numbering schemes for the same seven wires: the analyzer's pins are
`CH1..CH8`, PulseView names its inputs `D0..D7`, and the Nucleo's headers are
`D3..D9`. The map was confirmed from the signals rather than the labels, because
each task has an unmistakable signature.

| PulseView | Nucleo | Port | Signal | Signature |
|---|---|---|---|---|
| D0 | D3 | PB3 | `instr_samp` | dense 1 kHz train |
| D1 | D4 | PB5 | `instr_ctrl` | one pulse per ten of them |
| D2 | D5 | PB4 | `instr_cons` | flat, nothing typed |
| D3 | D6 | PB10 | `instr_tele` | one wide pulse per second |
| D4 | D7 | PA8 | `instr_flow` | flat until the jumper, then one per 2 s |
| D5 | D8 | PA9 | `instr_disp` | flat, HMI not compiled in |
| D6 | D9 | PC7 | `flow_pulse` | flat until the jumper, then 50 Hz |

PulseView `Dn` maps to Nucleo `D(n+3)`. Channels being flat is part of the
confirmation, not a fault.

</details>

<details>
<summary><b>Problems</b> (5)</summary>

<details>
<summary>We were working against the wrong board, and the ST-LINK told us</summary>

We had assumed the board on the desk was the STM32C0116-DK the course lends for
weeks 1 and 2, and the whole first pass of documents was written for it.

When it was plugged in, the ST-LINK's mass storage volume came up as:

```
DriveLetter  FileSystemLabel
E            NODE_L476RG
```

That label is written by the ST-LINK firmware and is board-specific. Confirmed
by `DETAILS.TXT` (ST-LINK V2J46M31) and by the single ST-LINK on the bus
(`0483:374b`). The board is a NUCLEO-L476RG.

The pin map, the flash budget and the meaning of one whole table row all change
with the board. Checking the probe's volume label takes two seconds and settles
it.

The correction was entirely in our favour. On the C0116-DK the display build
overflows (`region FLASH overflowed by 12800 bytes`, verified) and row 4
degenerates into a prefetch measurement, because `CONFIG_LAB_FLASH_CACHE_OFF`
declares `depends on SOC_SERIES_STM32L4X` and Kconfig drops it silently on a C0.
On the L476 the fragment does what the lab says. The six instrumentation pins
are also the unbroken Arduino run D3 to D8 here, instead of six scattered pins.

**This is worth passing to any pair measuring on a C0116-DK: their row 4 will be
a flash prefetch measurement, not a cache one, and nothing warns them.**

</details>

<details>
<summary>The SDK had no ARM toolchain, so no STM32 board could build at all</summary>

```
$ ls ~/zephyr-sdk-1.0.1/gnu
riscv64-zephyr-elf
```

Entry 01 ran on the ESP32-C6, which is RISC-V, so only that toolchain was ever
installed.

```bash
cd ~/zephyr-sdk-1.0.1 && ./setup.sh -t arm-zephyr-eabi
```

Before week 3: the ESP32-S3 is Xtensa, a third architecture, and needs
`xtensa-espressif_esp32s3_zephyr-elf` installed the same way. Doing it on lab day
costs the download.

</details>

<details>
<summary><code>west flash</code> has no runner on this host, and does not need one</summary>

`boards/st/nucleo_l476rg` offers the `openocd`, `stm32cubeprogrammer`, `jlink`
and `pyocd` runners. None of the underlying tools is installed here, and the
Zephyr SDK ships no OpenOCD in this install.

No tool is needed. The ST-LINK/V2-1 exposes a mass storage volume, so copying
`zephyr.bin` onto it programs the part. The file disappearing from the volume is
the success signal; a `FAIL.TXT` appearing is the error report. Neither `usbipd`
forwarding into WSL nor any driver install is involved, because the copy happens
from Windows.

</details>

<details>
<summary>One mini-USB cable, two devices that need one</summary>

The NUCLEO-L476RG and the logic analyzer both take mini-USB. Resolved by finding
a second cable, but it stops a session dead: the analyzer needs USB for power and
for streaming samples, and the board needs 5 V to run.

The way around, had no cable turned up: once programmed, the board does not need
the host, so any 5 V source on the CN6 pins frees the cable for the analyzer.
That covers a baseline capture but not Task C, where `calib` has to be typed on
the console while the capture runs.

</details>

<details>
<summary>The analyzer needs a driver swap before any software sees it</summary>

Plugged in, the clone enumerates as `0925:3881` and Windows reports it with
status `Error`: there is no in-box driver.

PulseView's installer bundles Zadig for this. With `Options → List All Devices`,
select the entry whose USB ID is exactly `0925 3881` and install **WinUSB**.
Afterwards:

```
Name: fx2lafw   Status: OK   Service: WinUSB
```

Care is required. With `List All Devices` ticked, Zadig lists every USB device on
the machine, including the keyboard, the mouse and the ST-LINK (`0483:374b`).
Replacing the driver of the wrong one breaks that device. The USB ID is the only
safe way to identify the target.

In PulseView, the driver to pick in step 1 of *Connect to Device* is
`fx2lafw (generic driver for FX2 based LAs)`, not the alphabetically first entry
the dialog opens on.

</details>

</details>

### Result

Every row of the week-2 table is measured. Full analysis in `ret.md` §3.

| # | Measurement | Value |
|---|---|---|
| 1 | Mean sampling period | 999.02 µs |
| 2 | Sampling jitter, max over 50 s | 6753.25 µs (10.75 µs in the clean regime) |
| 3 | Flow ISR to loop service | 9.67 µs (deterministic stimulus) |
| 4 | Sampling jitter, cache off | 119.25 µs clean regime, 11× row 2 |
| 5 | Sampling jitter during `calib` | 416.11 ms |
| 6 | `backlog_peak`, idle → `calib` | 6 → 416 ticks |

Measured `C_i`: sampling 4.95 µs, control 1.35 µs, telemetry 5980.36 µs, flow
batch 70.62 µs, flow ISR 11.50 µs. **Total utilisation 1.169 %.**

Four results worth carrying forward:

1. **The idle `backlog_peak` of 6 is the telemetry line.** 69 characters at
   115200 8N1 is 5.99 ms of polled-UART blocking; the analyzer measures the pulse
   at 5980.36 µs and counts exactly 6 catch-up periods after each one. The
   firmware's counter, the baud-rate arithmetic and the trace agree to better
   than 0.2 %. A soft task is eating a hard task's deadline at idle.
2. **`calib` is 416.11 ms of silence**, matching `backlog_peak = 416` and the
   hand calculation (1000 × 400 µs of `k_busy_wait` plus 1000 ADC reads at
   ~16 µs). The 416 queued samples are then taken inside 5.61 ms.
3. **One GPIO interrupt costs 11.50 µs and the control loop has 13.00 µs of
   margin.** Established by classifying control periods by whether a flow
   interrupt fired inside them, within the same capture: 0.0 % miss the deadline
   without one, 29.0 % with one. Connecting a sensor, changing no code, breaks
   REQ-CTRL-01.
4. **The ART accelerator was holding up REQ-CTRL-03 unrecorded.** Disabling it
   costs +47 % on `task_sampling` and +85.8 % on `task_control`, and pushes the
   clean-regime jitter from 10.75 µs to 119.25 µs, past the 100 µs budget. The
   telemetry task barely moves (+1.1 % once the data confound is removed),
   because its time is spent waiting on a UART, not executing.

| Check | Status |
|---|---|
| TASK 1, 2 and 3 completed | Done |
| Flow diagram, ten boxes, GPIOs marked | Done |
| RET §1: eight EARS requirements | Done, each with the origin of its number |
| RET §1: measured `C_i` for every task | Done |
| RET §3: rows 1 to 6 | **All measured** |
| Raw captures and reduction scripts committed | Done |

### Open items

- **Row 3 deserves a redo with an asynchronous source.** The jumper stimulus is
  phase-locked to the loop, so 9.67 µs is the deterministic case and not a worst
  case. A free-running square wave from a spare board would bound it properly.
- **`flow_isr` has no instrumentation GPIO**, so its 11.50 µs is inferred from
  the controlled comparison rather than measured directly. Adding a toggle there
  would confirm it.
- **`C_i` of `task_telemetry` is data-dependent** (5980 µs vs 6217 µs for the
  same code, because the printed values got longer). A WCET for it has to be
  bounded from the longest line the format string can produce, not from a
  typical run. Carry this into module 3.
- Optional extra, not part of the baseline: build with `display.conf` (47 372 B,
  fits here) and capture `instr_disp` next to `instr_samp`. It would add a third
  kind of blocker to the collection: UART-bound (telemetry), CPU-bound (`calib`)
  and I²C-bound (the 1 KB frame).
- REQ-CTRL-02 has no direct measurement: it is bounded by the control period
  (worst case 14.77 ms against a 5 ms deadline). Triggering a real overpressure
  and timing detection to actuation would measure it end to end.
- Add David and Ismael as collaborators on this repository.
- Install the Xtensa toolchain before week 3, and buy the ESP32-S3.
