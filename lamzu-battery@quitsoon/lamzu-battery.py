#!/usr/bin/env python3
"""Print the battery level of a Lamzu mouse (VID 0x373E) on Linux.

Port of Sheroune/lamzu-battery-monitory. Talks to the hidraw node directly
through ioctls, so there are no third-party dependencies.

Usage:
    lamzu-battery.py                 -> "87%" or "87% (charging)"
    lamzu-battery.py --json          -> {"percent": 87, "charging": false, "mode": "dongle"}
    lamzu-battery.py --watch 30      -> refresh every 30 s
    lamzu-battery.py --debug         -> list matching hidraw nodes

Exit code: 0 = ok, 1 = mouse not found / no valid response, 2 = permission denied.
"""
import argparse
import fcntl
import glob
import json
import os
import sys
import time

VENDOR_ID = 0x373E
PRODUCT_IDS = {0x001E: "dongle", 0x001C: "wired"}
INTERFACE = 2
USAGE_PAGE = 0xFFFF


# --- hidraw ioctls: HIDIOCSFEATURE(len) / HIDIOCGFEATURE(len) --------------
def _hid_ioc(nr, size):
    return (3 << 30) | (size << 16) | (ord("H") << 8) | nr  # _IOWR('H', nr, len)


def HIDIOCSFEATURE(n):
    return _hid_ioc(0x06, n)


def HIDIOCGFEATURE(n):
    return _hid_ioc(0x07, n)


# --- device discovery via sysfs -------------------------------------------
def _read(path, mode="r"):
    try:
        with open(path, mode) as f:
            return f.read()
    except OSError:
        return None


def _usage_page(desc):
    """Usage page of the first item in a HID report descriptor."""
    if not desc:
        return None
    if desc[0] == 0x05 and len(desc) >= 2:
        return desc[1]
    if desc[0] == 0x06 and len(desc) >= 3:
        return desc[1] | (desc[2] << 8)
    return None


def find_devices():
    """Return [(mode, /dev/hidrawN)] for the vendor-defined interface 2."""
    found = []
    for node in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        dev = os.path.realpath(os.path.join(node, "device"))
        uevent = _read(os.path.join(dev, "uevent")) or ""
        hid_id = next((l.split("=", 1)[1] for l in uevent.splitlines()
                       if l.startswith("HID_ID=")), "")
        try:
            _, vid, pid = (int(x, 16) for x in hid_id.split(":"))
        except ValueError:
            continue
        if vid != VENDOR_ID or pid not in PRODUCT_IDS:
            continue
        iface = _read(os.path.join(dev, "..", "bInterfaceNumber"))
        if iface is None or int(iface.strip(), 16) != INTERFACE:
            continue
        if _usage_page(_read(os.path.join(dev, "report_descriptor"), "rb")) != USAGE_PAGE:
            continue
        found.append((PRODUCT_IDS[pid], "/dev/" + os.path.basename(node)))
    return found


# --- battery query --------------------------------------------------------
def query(path, retries=3):
    """Send the battery command; return {"percent", "charging"} or None."""
    fd = os.open(path, os.O_RDWR)
    try:
        for _ in range(retries):
            req = bytearray(65)
            req[0] = 0x00  # report ID
            req[3] = 0x02  # device ID
            req[4] = 0x02  # length
            req[6] = 0x83  # battery command
            fcntl.ioctl(fd, HIDIOCSFEATURE(65), bytes(req))
            time.sleep(0.1)

            resp = bytearray(65)  # resp[0] = report ID 0
            fcntl.ioctl(fd, HIDIOCGFEATURE(65), resp)
            if resp[1] == 0xA1 and resp[6] == 0x83:
                return {"percent": resp[8], "charging": resp[7] == 1}
            time.sleep(0.2)
    except OSError:
        return None
    finally:
        os.close(fd)
    return None


def read_battery():
    for mode, path in find_devices():
        try:
            result = query(path)
        except PermissionError:
            raise
        if result:
            result["mode"] = mode
            return result
    return None


def render(result, as_json):
    if result is None:
        return json.dumps({"connected": False}) if as_json else "disconnected"
    if as_json:
        return json.dumps(result)
    return f"{result['percent']}%" + (" (charging)" if result["charging"] else "")


def main():
    ap = argparse.ArgumentParser(description="Lamzu mouse battery (Linux)")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--watch", type=float, metavar="SECONDS", help="repeat forever")
    ap.add_argument("--debug", action="store_true", help="list matching hidraw nodes")
    args = ap.parse_args()

    if args.debug:
        devs = find_devices()
        print(devs or "no matching hidraw node (VID 373E, PID 001E/001C, iface 2, usage page FFFF)")

    try:
        while True:
            result = read_battery()
            print(render(result, args.json), flush=True)
            if not args.watch:
                return 0 if result else 1
            time.sleep(args.watch)
    except PermissionError:
        print("permission denied on /dev/hidraw*: add the udev rule (see README/notes)",
              file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
