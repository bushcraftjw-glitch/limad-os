import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

function launch(argv) {
    try {
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
    } catch (error) {
        Main.notifyError('LiLink', error.message);
    }
}

export default class LiLinkExtension extends Extension {
    enable() {
        this._indicator = new PanelMenu.Button(0.0, 'LiLink', false);
        this._indicator.accessible_name = 'LiLink';
        this._icon = new St.Icon({gicon: Gio.icon_new_for_string(`${this.path}/icons/lilink-symbolic.svg`), style_class: 'system-status-icon'});
        this._indicator.add_child(this._icon);
        this._status = new PopupMenu.PopupMenuItem('LiLink wird geprüft …', {reactive: false});
        this._indicator.menu.addMenuItem(this._status);
        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const open = new PopupMenu.PopupMenuItem('LiLink öffnen');
        open.connect('activate', () => launch(['/usr/local/bin/lilink']));
        this._indicator.menu.addMenuItem(open);
        const remote = new PopupMenu.PopupMenuItem('Remote-Desktop-Einstellungen');
        remote.connect('activate', () => launch(['/usr/bin/gnome-control-center', 'system', 'remote-desktop']));
        this._indicator.menu.addMenuItem(remote);
        this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        const restart = new PopupMenu.PopupMenuItem('LiLink-Dienst neu starten');
        restart.connect('activate', () => launch(['/usr/bin/systemctl', '--user', 'restart', 'limad-link.service']));
        this._indicator.menu.addMenuItem(restart);
        Main.panel.addToStatusArea('lilink', this._indicator, 2, 'right');
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 5, () => {
            this._update();
            return GLib.SOURCE_CONTINUE;
        });
        this._update();
    }

    _update() {
        try {
            const runtime = GLib.build_filenamev([GLib.get_user_runtime_dir(), 'limad-link.json']);
            const file = Gio.File.new_for_path(runtime);
            if (!file.query_exists(null)) {
                this._status.label.text = 'LiLink-Dienst wird gestartet';
                launch(['/usr/bin/systemctl', '--user', 'start', 'limad-link.service']);
                return;
            }
            const [, contents] = file.load_contents(null);
            const data = JSON.parse(new TextDecoder().decode(contents));
            this._status.label.text = data.version ? `Bereit · ${data.version}` : 'LiLink ist bereit';
        } catch (error) {
            this._status.label.text = 'LiLink-Status nicht verfügbar';
        }
    }

    disable() {
        if (this._timer) {
            GLib.source_remove(this._timer);
            this._timer = 0;
        }
        this._indicator?.destroy();
        this._indicator = null;
    }
}
