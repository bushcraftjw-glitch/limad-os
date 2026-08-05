import Gio from 'gi://Gio';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

function launch(argv) {
    try {
        Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
    } catch (error) {
        Main.notifyError('LiDrop', error.message);
        console.error(`LiDrop launch failed: ${error.stack ?? error.message}`);
    }
}

export default class LiDropExtension extends Extension {
    enable() {
        try {
            this._indicator = new PanelMenu.Button(0.0, 'LiDrop', false);
            this._indicator.accessible_name = 'LiDrop';
            const icon = new St.Icon({
                gicon: Gio.icon_new_for_string(`${this.path}/icons/lidrop-symbolic.svg`),
                style_class: 'system-status-icon',
            });
            this._indicator.add_child(icon);

            const open = new PopupMenu.PopupMenuItem('LiDrop öffnen');
            open.connect('activate', () => launch(['/usr/local/bin/limad-drop']));
            this._indicator.menu.addMenuItem(open);

            const folder = new PopupMenu.PopupMenuItem('LiDrop-Ordner öffnen');
            folder.connect('activate', () => launch(['/usr/local/bin/limad-open-drop-folder']));
            this._indicator.menu.addMenuItem(folder);
            this._indicator.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

            const restart = new PopupMenu.PopupMenuItem('LiDrop-Dienst neu starten');
            restart.connect('activate', () => launch(['/usr/bin/systemctl', '--user', 'restart', 'limad-drop.service']));
            this._indicator.menu.addMenuItem(restart);

            Main.panel.addToStatusArea('lidrop', this._indicator, 1, 'right');
            console.log('LiDrop status indicator enabled');
        } catch (error) {
            this._indicator?.destroy();
            this._indicator = null;
            Main.notifyError('LiDrop-Statussymbol konnte nicht geladen werden', error.message);
            console.error(`LiDrop extension enable failed: ${error.stack ?? error.message}`);
            throw error;
        }
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
