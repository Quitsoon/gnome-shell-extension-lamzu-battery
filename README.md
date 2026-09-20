# Lamzu Battery – GNOME Shell extension

Shows the battery level of a Lamzu mouse in the GNOME top bar.

- Percentage next to a mouse icon, colored by level (green / yellow / red)
- ⚡ indicator while charging
- Desktop notifications when the mouse is fully charged or running low
- Works with the wireless dongle and with the wired connection
- Click the icon to see the status and refresh manually

The extension calls a small Python script (`lamzu-battery.py`) that talks to the
mouse's `hidraw` node directly. There are no third-party dependencies.

## Requirements

- GNOME Shell 45 to 51
- `python3`
- A Lamzu mouse with USB vendor ID `373E` (dongle: product ID `001E`, wired: `001C`)

## Installation

**1. Get the files and copy them to the gnome extension folder**

```bash
git clone https://github.com/Quitsoon/gnome-shell-extension-lamzu-battery
cp -r gnome-shell-extension-lamzu-battery/lamzu-battery@quitsoon ~/.local/share/gnome-shell/extensions/
```

**2. Copy the udev rule**

Without it, the script can't read the mouse and the extension shows a red `!`.

I used this repo : [passionofcrisis/Lamzu-Webdriver-Aurora-Linux-fix](https://github.com/passionofcrisis/Lamzu-Webdriver-Aurora-Linux-fix)
This one should work too : [ak4duy/lamzu-linux-udev](https://github.com/ak4duy/lamzu-linux-udev)

**3. Restart GNOME Shell and enable the extension**

- Wayland: log out and back in
- X11: press `Alt+F2`, type `r`, press Enter

```bash
gnome-extensions enable lamzu-battery@quitsoon
```

## Usage

The top bar shows the current level. Values:

| Display | Meaning |
|---------|---------|
| `87%` | Battery level (green above 50%, yellow up to 50%, red at 20% or below) |
| `87% ⚡` | Charging |
| `--` | Mouse not found or asleep |
| `!` | No permission on `/dev/hidraw*` (udev rule missing) |

The level is refreshed every 60 seconds while discharging, and every 15 seconds while
charging or when the mouse can't be found.

### Command line

The script also works on its own:

```bash
python3 lamzu-battery.py              # 87% or 87% (charging)
python3 lamzu-battery.py --json       # {"percent": 87, "charging": false, "mode": "dongle"}
python3 lamzu-battery.py --watch 30   # refresh every 30 s
python3 lamzu-battery.py --debug      # list matching hidraw nodes
```

Exit codes: `0` ok, `1` mouse not found or no valid response, `2` permission denied.

## Troubleshooting

- **Red `!` in the top bar**: the udev rule is missing or wasn't applied. Redo step 2 and replug the mouse.
- **`--` in the top bar**: run `python3 lamzu-battery.py --debug`. If it lists no hidraw node, the mouse isn't detected (asleep, unplugged, or a different vendor/product ID).
- **Extension doesn't appear**: check that the folder name matches the `uuid` in `metadata.json`, then restart the shell. `journalctl -f -o cat /usr/bin/gnome-shell` shows errors.

## Uninstall

```bash
gnome-extensions disable lamzu-battery@quitsoon
rm -rf ~/.local/share/gnome-shell/extensions/lamzu-battery@quitsoon
sudo rm /etc/udev/rules.d/99-lamzu.rules
```

## Credits

The HID protocol handling in `lamzu-battery.py` is a Linux port of
[Sheroune/lamzu-battery-monitory](https://github.com/Sheroune/lamzu-battery-monitory) (MIT).

## License

[MIT](LICENSE)
