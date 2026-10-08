"""Drives the node's console during an analyzer capture and logs everything.

It replaces typing by hand: the commands land at the same offsets in every
capture, and the log always starts with the boot banner that proves which
firmware was on the board.

Usage (inside the Zephyr venv, which brings pyserial):
    python capture_console.py <log.txt> baseline
    python capture_console.py <log.txt> calib
    python capture_console.py <log.txt> calib-threads

baseline       : sends nothing for the whole capture (the protocol forbids input)
calib          : status at +5 s, calib at +28 s, status after "calibration done"
calib-threads  : the same, then `threads` once the 50 s capture is over
"""
import os
import sys
import time
import threading
import re

import serial

PORT = os.environ.get("CONSOLE_PORT", "/dev/ttyACM0")   # override to test on native_sim
BAUD = 115200
CAPTURE_S = 52          # PulseView runs 49.999 s; a little margin
log_path, mode = sys.argv[1], sys.argv[2]
assert mode in ("baseline", "calib", "calib-threads"), mode

ser = serial.Serial()
ser.port, ser.baudrate, ser.timeout = PORT, BAUD, 0.1
ser.dtr = ser.rts = False   # keep the auto-reset circuit idle on open
ser.open()

log = open(log_path, "w", encoding="utf-8")
lines, stop = [], threading.Event()


def reader():
    buf = b""
    while not stop.is_set():
        buf += ser.read(256)
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            text = raw.decode("utf-8", "replace").rstrip("\r")
            lines.append(text)
            log.write(text + "\n")
            log.flush()
            print("   | " + text, flush=True)


def send(cmd):
    print(">>> " + cmd, flush=True)
    ser.write(cmd.encode() + b"\r")


def wait_for(pattern, timeout):
    t0, start = time.time(), len(lines)
    while time.time() - t0 < timeout:
        if any(re.search(pattern, l) for l in lines[start:]):
            return True
        time.sleep(0.05)
    return False


threading.Thread(target=reader, daemon=True).start()

print("\n=== Press RST on the board now (waiting up to 30 s for the banner) ===")
if not wait_for(r"build \(", 30):
    sys.exit("no boot banner seen: check the port and press RST again")
banner = next(l for l in lines if "build (" in l)
print("\n=== Firmware on the board: " + banner.split("Control")[-1].strip(" :—"))

if mode != "baseline":
    print("\n=== Checking the GPIO2 -> GPIO11 jumper ===")
    counts = []
    for _ in range(2):
        start = len(lines)
        send("status")
        wait_for(r"batches=", 2)
        m = [re.search(r"batches=(\d+)", l) for l in lines[start:]]
        counts += [int(x.group(1)) for x in m if x]
        time.sleep(3)
    if len(counts) >= 2 and counts[-1] > counts[0]:
        print("=== Jumper OK: batches %d -> %d" % (counts[0], counts[-1]))
    else:
        print("=== WARNING: batches did not go up %s. Check the jumper." % counts)

input("\n=== Press Enter, then click Run in PulseView right away ===")
t0 = time.time()
at = lambda s: time.sleep(max(0, t0 + s - time.time()))

if mode == "baseline":
    print("=== Capturing: no input for %d s" % CAPTURE_S)
else:
    at(5)
    send("status")
    at(28)
    send("calib")
    if not wait_for(r"calibration done", 15):
        print("=== WARNING: no 'calibration done' within 15 s")
    send("status")
at(CAPTURE_S)
print("\n=== Capture window over: export the VCD in PulseView now ===")

if mode == "calib-threads":
    send("threads")
    time.sleep(3)

stop.set()
time.sleep(0.3)
ser.close()
log.close()
print("=== Log saved to " + log_path)
