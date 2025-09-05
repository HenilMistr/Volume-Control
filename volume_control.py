import tkinter as tk
from tkinter import ttk, messagebox
from pycaw.pycaw import AudioUtilities
import keyboard
import json
import os
import sys
import threading
import time
import pystray
from PIL import Image, ImageDraw
import winreg

CONFIG_FILE = "hotkeys.json"
APP_NAME = "VolumeController"

# ---------- Config Management ----------
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    else:
        return {
            "apps": {},
            "settings": {
                "remember_volumes": True,
                "auto_start": False
            }
        }

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# ---------- Autostart ----------
def get_executable_path():
    if getattr(sys, "frozen", False):
        return sys.executable  # If compiled into exe
    else:
        return sys.executable + " " + os.path.abspath(__file__)

def enable_autostart():
    path = get_executable_path()
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0, winreg.KEY_SET_VALUE
    )
    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, path)
    winreg.CloseKey(key)

def disable_autostart():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass

def is_autostart_enabled():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ
        )
        value, _ = winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True if value else False
    except FileNotFoundError:
        return False

# ---------- Audio Sessions ----------
def get_active_sessions():
    return [s for s in AudioUtilities.GetAllSessions() if s.Process]

def get_active_apps():
    return [s.Process.name() for s in get_active_sessions()]

def find_session(app_name):
    for session in get_active_sessions():
        if session.Process and session.Process.name().lower() == app_name.lower():
            return session
    return None

# ---------- Volume Controls ----------
def adjust_volume(session, delta):
    if not session:
        return
    volume = session.SimpleAudioVolume
    new_vol = max(0.0, min(1.0, volume.GetMasterVolume() + delta))
    volume.SetMasterVolume(new_vol, None)

def set_volume(session, level):
    if not session:
        return
    session.SimpleAudioVolume.SetMasterVolume(level / 100, None)

def toggle_mute(session):
    if not session:
        return
    current = session.SimpleAudioVolume.GetMute()
    session.SimpleAudioVolume.SetMute(0 if current else 1, None)

# ---------- Hotkeys ----------
def setup_hotkeys(config):
    for app_name, keys in config.get("apps", {}).items():
        session = find_session(app_name)
        if not session:
            continue
        if "vol_up" in keys:
            keyboard.add_hotkey(keys["vol_up"], lambda s=session: adjust_volume(s, +0.1))
        if "vol_down" in keys:
            keyboard.add_hotkey(keys["vol_down"], lambda s=session: adjust_volume(s, -0.1))
        if "mute" in keys:
            keyboard.add_hotkey(keys["mute"], lambda s=session: toggle_mute(s))

# ---------- GUI ----------
class VolumeHotkeyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎹 Per-App Volume Mixer")
        self.root.geometry("700x500")

        self.config = load_config()
        self.active_apps = []
        self.sliders = {}
        self.mute_buttons = {}
        self.listbox = None

        # Menu bar (Settings)
        menubar = tk.Menu(root)
        settings_menu = tk.Menu(menubar, tearoff=0)

        self.remember_var = tk.BooleanVar(value=self.config["settings"].get("remember_volumes", True))
        self.autostart_var = tk.BooleanVar(value=is_autostart_enabled())

        settings_menu.add_checkbutton(
            label="Remember volumes & mute state",
            variable=self.remember_var,
            command=self.toggle_remember_setting
        )
        settings_menu.add_checkbutton(
            label="Auto-start with Windows",
            variable=self.autostart_var,
            command=self.toggle_autostart_setting
        )

        menubar.add_cascade(label="Settings", menu=settings_menu)
        root.config(menu=menubar)

        # Mixer frame
        self.mixer_frame = tk.Frame(root)
        self.mixer_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Bottom controls
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=5)

        self.listbox = tk.Listbox(btn_frame, height=5, exportselection=False)
        self.listbox.pack(side=tk.LEFT, padx=5)

        btns = tk.Frame(btn_frame)
        btns.pack(side=tk.LEFT)
        tk.Button(btns, text="Set Hotkeys", command=self.set_hotkeys).pack(fill=tk.X, pady=2)
        tk.Button(btns, text="Refresh Apps", command=self.refresh_apps).pack(fill=tk.X, pady=2)
        tk.Button(btns, text="Minimize to Tray", command=self.minimize_to_tray).pack(fill=tk.X, pady=2)

        self.refresh_apps()

        # Background threads
        threading.Thread(target=self.run_hotkeys, daemon=True).start()
        threading.Thread(target=self.update_volumes, daemon=True).start()

    # ---------- Settings ----------
    def toggle_remember_setting(self):
        self.config["settings"]["remember_volumes"] = self.remember_var.get()
        save_config(self.config)

    def toggle_autostart_setting(self):
        if self.autostart_var.get():
            enable_autostart()
        else:
            disable_autostart()
        self.config["settings"]["auto_start"] = self.autostart_var.get()
        save_config(self.config)

    # ---------- App Controls ----------
    def refresh_apps(self):
        self.active_apps = get_active_apps()
        for widget in self.mixer_frame.winfo_children():
            widget.destroy()
        self.sliders.clear()
        self.mute_buttons.clear()
        self.listbox.delete(0, tk.END)

        for app in self.active_apps:
            frame = tk.Frame(self.mixer_frame)
            frame.pack(fill=tk.X, pady=5)

            label = tk.Label(frame, text=app, width=20, anchor="w")
            label.pack(side=tk.LEFT)

            slider = tk.Scale(frame, from_=0, to=100, orient=tk.HORIZONTAL,
                              command=lambda val, a=app: self.on_slider_change(a, val))
            slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

            mute_btn = tk.Button(frame, text="Mute", width=8,
                                 command=lambda a=app: self.on_toggle_mute(a))
            mute_btn.pack(side=tk.LEFT, padx=5)

            hotkeys = self.config.get("apps", {}).get(app, {})
            hotkey_label = tk.Label(frame, text=str(hotkeys), width=20, anchor="e")
            hotkey_label.pack(side=tk.RIGHT)

            self.sliders[app] = slider
            self.mute_buttons[app] = mute_btn
            self.listbox.insert(tk.END, app)

    def on_slider_change(self, app_name, val):
        session = find_session(app_name)
        if session:
            set_volume(session, int(val))
            if self.remember_var.get():
                self.config.setdefault("apps", {}).setdefault(app_name, {})["volume"] = int(val)
                save_config(self.config)

    def on_toggle_mute(self, app_name):
        session = find_session(app_name)
        if session:
            toggle_mute(session)
            if self.remember_var.get():
                muted = session.SimpleAudioVolume.GetMute()
                self.config.setdefault("apps", {}).setdefault(app_name, {})["muted"] = bool(muted)
                save_config(self.config)

    def set_hotkeys(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an app from the list first.")
            return
        app_name = self.listbox.get(selection[0])

        messagebox.showinfo("Hotkey Capture", f"Press hotkey for VOLUME UP for {app_name}")
        vol_up = keyboard.read_hotkey(suppress=False)

        messagebox.showinfo("Hotkey Capture", f"Press hotkey for VOLUME DOWN for {app_name}")
        vol_down = keyboard.read_hotkey(suppress=False)

        messagebox.showinfo("Hotkey Capture", f"Press hotkey for MUTE for {app_name}")
        mute = keyboard.read_hotkey(suppress=False)

        self.config.setdefault("apps", {})[app_name] = {
            "vol_up": vol_up, "vol_down": vol_down, "mute": mute
        }
        save_config(self.config)
        self.refresh_apps()
        messagebox.showinfo("Success", f"Hotkeys set for {app_name}")

    def run_hotkeys(self):
        while True:
            setup_hotkeys(self.config)
            time.sleep(10)

    def update_volumes(self):
        while True:
            for app, slider in self.sliders.items():
                session = find_session(app)
                if session:
                    vol = int(session.SimpleAudioVolume.GetMasterVolume() * 100)
                    if slider.get() != vol:
                        slider.set(vol)
                    muted = session.SimpleAudioVolume.GetMute()
                    btn = self.mute_buttons[app]
                    btn.config(text="Unmute" if muted else "Mute")
            time.sleep(1)

    def minimize_to_tray(self):
        self.root.withdraw()
        self.create_tray_icon()

    def create_tray_icon(self):
        image = Image.new("RGB", (64, 64), (0, 0, 0))
        d = ImageDraw.Draw(image)
        d.rectangle([16, 24, 48, 40], fill=(255, 255, 255))

        def show_window(icon, item):
            self.root.after(0, self.root.deiconify)
            icon.stop()

        def quit_app(icon, item):
            icon.stop()
            self.root.quit()

        menu = pystray.Menu(
            pystray.MenuItem("Show", show_window),
            pystray.MenuItem("Quit", quit_app)
        )
        icon = pystray.Icon(APP_NAME, image, "Volume Controller", menu)
        threading.Thread(target=icon.run, daemon=True).start()

# ---------- Main ----------
if __name__ == "__main__":
    root = tk.Tk()
    app = VolumeHotkeyApp(root)
    root.mainloop()
