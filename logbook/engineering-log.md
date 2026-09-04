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
