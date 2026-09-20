import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const POLL_SECONDS = 60;   // while discharging
const FAST_SECONDS = 15;   // while charging / mouse absent

export default class LamzuBattery extends Extension {
    enable() {
        this._cancellable = new Gio.Cancellable();
        this._timer = 0;
        this._busy = false;
        this._fullNotified = false;
        this._lowNotified = false;

        this._button = new PanelMenu.Button(0.0, 'Lamzu Battery', false);
        const box = new St.BoxLayout({style_class: 'panel-status-menu-box'});
        box.add_child(new St.Icon({
            icon_name: 'input-mouse-symbolic',
            style_class: 'system-status-icon',
        }));
        this._label = new St.Label({
            text: '--',
            y_align: Clutter.ActorAlign.CENTER,
        });
        box.add_child(this._label);
        this._button.add_child(box);

        this._status = new PopupMenu.PopupMenuItem('Reading battery...', {reactive: false});
        this._button.menu.addMenuItem(this._status);
        this._button.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const refresh = new PopupMenu.PopupMenuItem('Refresh now');
        refresh.connect('activate', () => this._refresh());
        this._button.menu.addMenuItem(refresh);

        Main.panel.addToStatusArea(this.uuid, this._button);
        this._refresh();
    }

    disable() {
        this._cancellable?.cancel();
        this._cancellable = null;
        if (this._timer) {
            GLib.source_remove(this._timer);
            this._timer = 0;
        }
        this._button?.destroy();
        this._button = null;
        this._label = null;
        this._status = null;
    }

    _refresh() {
        if (this._timer) {
            GLib.source_remove(this._timer);
            this._timer = 0;
        }
        if (this._busy)
            return;
        this._busy = true;

        try {
            const script = GLib.build_filenamev([this.path, 'lamzu-battery.py']);
            const proc = Gio.Subprocess.new(
                ['python3', script, '--json'],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);
            proc.communicate_utf8_async(null, this._cancellable, (p, res) => {
                let code = -1;
                let out = '';
                try {
                    [, out] = p.communicate_utf8_finish(res);
                    code = p.get_exit_status();
                } catch (e) {
                    if (e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                        return; // extension was disabled
                }
                this._busy = false;
                this._apply(code, out);
            });
        } catch (e) {
            this._busy = false;
            this._apply(-1, '');
        }
    }

    _apply(code, out) {
        if (!this._button)
            return;

        let next = FAST_SECONDS;
        if (code === 0) {
            try {
                const r = JSON.parse(out);
                this._show(r);
                next = r.charging ? FAST_SECONDS : POLL_SECONDS;
            } catch (e) {
                this._setState('--', 'Unexpected reply from lamzu-battery.py', '');
            }
        } else if (code === 2) {
            this._setState('!', 'No permission on /dev/hidraw* (udev rule missing)', 'color: #ff5555;');
            next = POLL_SECONDS;
        } else {
            this._setState('--', 'Mouse not found or asleep', 'color: #9a9996;');
        }

        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, next, () => {
            this._timer = 0;
            this._refresh();
            return GLib.SOURCE_REMOVE;
        });
    }

    _show(r) {
        const p = Math.min(r.percent, 100);
        const color = p <= 20 ? '#ff5555' : p <= 50 ? '#f5c211' : '#3ddc84';
        const text = `${p}%${r.charging ? ' \u26A1' : ''}`;
        const status = `Battery: ${p}%${r.charging ? ' - charging' : ''} (${r.mode})`;
        this._setState(text, status, `color: ${color};`);

        if (p >= 100 && (r.charging || r.mode === 'wired')) {
            if (!this._fullNotified) {
                Main.notify('Mouse fully charged', 'Lamzu battery is at 100%.');
                this._fullNotified = true;
            }
        } else if (p < 95) {
            this._fullNotified = false;
        }

        if (p <= 15 && !r.charging) {
            if (!this._lowNotified) {
                Main.notify('Mouse battery low', `Lamzu battery is at ${p}%.`);
                this._lowNotified = true;
            }
        } else if (p > 20 || r.charging) {
            this._lowNotified = false;
        }
    }

    _setState(text, status, style) {
        this._label.set_text(text);
        this._label.set_style(style);
        this._status.label.set_text(status);
    }
}
