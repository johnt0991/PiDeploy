import json
import os
import stat
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from datetime import datetime

import paramiko
from scp import SCPClient


# === RETRO 80s THEME COLORS ===
BG_DARK = "#0d0d0d"
BG_MED = "#1a1a2e"
BG_LIGHT = "#16213e"
NEON_PINK = "#ff00ff"
NEON_CYAN = "#00ffff"
NEON_GREEN = "#39ff14"
NEON_PURPLE = "#bf00ff"
NEON_YELLOW = "#ffff00"
NEON_ORANGE = "#ff6600"
TEXT_WHITE = "#ffffff"
TEXT_GRAY = "#888888"


APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(APP_DIR, "deploy_tool_settings.json")

REMOTE_BASE = "/srv/pi-monitor-deploy"
REMOTE_HARDWARE_DIR = "/srv/samba/share/pi_housing_code"
REMOTE_DOCKER_DIR = "/srv/docker/compose/core"
REMOTE_GLANCE_CONFIG = "/srv/docker/data/glance/config"
REMOTE_GLANCE_ASSETS = "/srv/docker/data/glance/assets"
REMOTE_KUMA_DATA = "/srv/docker/data/kuma"


DEFAULT_SETTINGS = {
    "pi_ip": "10.0.0.46",
    "username": "John",
    "password": "",
    "save_password": False,
    "deployment_folder": "",
    "hardware_script": "",
    "docker_compose": "",
    "glance_config_folder": "",
    "glance_assets_folder": "",
    "kuma_backup_folder": "",
    "systemd_service_file": "",
}


class RetroButton(tk.Frame):
    """Cross-platform retro button built from basic Tk widgets."""
    def __init__(self, master, **kwargs):
        self.accent = kwargs.pop("bg_color", NEON_CYAN)
        self.command = kwargs.pop("command", None)
        text = kwargs.pop("text", "")
        font = kwargs.pop("font", ("Courier New", 10, "bold"))
        width = kwargs.pop("width", None)
        height = kwargs.pop("height", None)
        padx = kwargs.pop("padx", 15)
        pady = kwargs.pop("pady", 5)
        cursor = kwargs.pop("cursor", "hand2")
        anchor = kwargs.pop("anchor", "center")
        self.normal_bg = kwargs.pop("bg", BG_DARK)

        super().__init__(
            master,
            bg=self.normal_bg,
            relief="flat",
            bd=2,
            highlightthickness=1,
            highlightcolor=self.accent,
            highlightbackground=self.normal_bg,
            cursor=cursor,
        )
        self.label = tk.Label(
            self,
            text=text,
            bg=self.normal_bg,
            fg=self.accent,
            font=font,
            cursor=cursor,
            padx=padx,
            pady=pady,
            anchor=anchor,
        )
        self.label.pack(fill="both", expand=True)

        if width is not None:
            self.label.config(width=width)
        if height is not None:
            self.label.config(height=height)

        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.label.bind("<Enter>", self.on_enter)
        self.label.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        self.label.bind("<Button-1>", self.on_click)
        self.bind("<Return>", self.on_click)
        self.bind("<space>", self.on_click)

        if kwargs:
            self.config(**kwargs)

    def on_enter(self, _event=None):
        super().configure(bg=self.accent, highlightbackground=self.accent)
        self.label.configure(bg=self.accent, fg=BG_DARK)

    def on_leave(self, _event=None):
        super().configure(bg=self.normal_bg, highlightbackground=self.normal_bg)
        self.label.configure(bg=self.normal_bg, fg=self.accent)

    def on_click(self, _event=None):
        if self.command:
            self.command()

    def configure(self, cnf=None, **kwargs):
        options = {}
        if cnf:
            options.update(cnf)
        options.update(kwargs)

        label_options = {}
        frame_options = {}

        if "command" in options:
            self.command = options.pop("command")
        if "text" in options:
            label_options["text"] = options.pop("text")
        if "font" in options:
            label_options["font"] = options.pop("font")
        if "width" in options:
            label_options["width"] = options.pop("width")
        if "height" in options:
            label_options["height"] = options.pop("height")
        if "fg" in options:
            self.accent = options.pop("fg")
            label_options["fg"] = self.accent
            frame_options["highlightcolor"] = self.accent
        if "bg_color" in options:
            self.accent = options.pop("bg_color")
            label_options["fg"] = self.accent
            frame_options["highlightcolor"] = self.accent
        if "bg" in options:
            self.normal_bg = options.pop("bg")
            frame_options["bg"] = self.normal_bg
            frame_options["highlightbackground"] = self.normal_bg
            label_options["bg"] = self.normal_bg
        if "padx" in options:
            label_options["padx"] = options.pop("padx")
        if "pady" in options:
            label_options["pady"] = options.pop("pady")
        if "anchor" in options:
            label_options["anchor"] = options.pop("anchor")

        for ignored in ("activebackground", "activeforeground", "relief", "bd"):
            options.pop(ignored, None)

        frame_options.update(options)
        if frame_options:
            super().configure(**frame_options)
        if label_options:
            self.label.configure(**label_options)

    config = configure


class RetroEntry(tk.Entry):
    """Retro 80s style entry field"""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.config(
            bg=BG_LIGHT,
            fg=NEON_CYAN,
            insertbackground=NEON_PINK,
            relief="flat",
            bd=2,
            highlightthickness=1,
            highlightcolor=NEON_PINK,
            highlightbackground=BG_MED,
            font=("Courier New", 10),
        )


class RetroCheckbutton(tk.Frame):
    """Cross-platform checkbox with fixed retro styling."""
    def __init__(self, master, text="", variable=None, **kwargs):
        self.variable = variable or tk.BooleanVar()
        cursor = kwargs.pop("cursor", "hand2")
        super().__init__(master, bg=BG_DARK, cursor=cursor)

        self.box = tk.Label(
            self,
            bg=BG_DARK,
            fg=NEON_YELLOW,
            font=("Courier New", 11, "bold"),
            cursor=cursor,
            width=2,
        )
        self.box.pack(side="left")

        self.label = tk.Label(
            self,
            text=text,
            bg=BG_DARK,
            fg=NEON_YELLOW,
            font=("Courier New", 10),
            cursor=cursor,
        )
        self.label.pack(side="left", padx=(4, 0))

        self.bind("<Button-1>", self.toggle)
        self.box.bind("<Button-1>", self.toggle)
        self.label.bind("<Button-1>", self.toggle)
        self.variable.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def toggle(self, _event=None):
        self.variable.set(not self.variable.get())

    def refresh(self):
        self.box.config(text="■" if self.variable.get() else "□")


class RetroLabel(tk.Label):
    """Retro 80s style label"""
    def __init__(self, master, text="", font_size=12, color=NEON_CYAN, **kwargs):
        super().__init__(master, text=text, **kwargs)
        self.config(
            bg=BG_DARK,
            fg=color,
            font=("Courier New", font_size, "bold" if font_size > 14 else "normal"),
        )


class RetroFrame(tk.Frame):
    """Retro 80s style frame with border"""
    def __init__(self, master, border_color=NEON_PURPLE, **kwargs):
        super().__init__(master, **kwargs)
        self.config(
            bg=BG_DARK,
            relief="flat",
            bd=3,
            highlightthickness=0,
        )
        # Add decorative border frame
        border = tk.Frame(self, bg=border_color, bd=0)
        border.place(relx=0, rely=0, relwidth=1, relheight=1)
        inner = tk.Frame(border, bg=BG_DARK, bd=0)
        inner.place(relx=0.005, rely=0.02, relwidth=0.99, relheight=0.96)


class PiDeployTool:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ Pi Monitor Deploy Tool ⚡")
        self.root.geometry("950x700")
        self.root.configure(bg=BG_DARK)

        # Set window icon (if available) and style
        try:
            self.root.iconbitmap("deploy_icon.ico")
        except:
            pass

        self.settings = DEFAULT_SETTINGS.copy()
        self.load_settings()

        self.pi_ip = tk.StringVar(value=self.settings["pi_ip"])
        self.username = tk.StringVar(value=self.settings["username"])
        self.password = tk.StringVar(value=self.settings.get("password", ""))
        self.save_password = tk.BooleanVar(value=self.settings.get("save_password", False))

        self.path_vars = {
            key: tk.StringVar(value=self.settings.get(key, ""))
            for key in [
                "hardware_script",
                "docker_compose",
                "glance_config_folder",
                "glance_assets_folder",
                "kuma_backup_folder",
                "systemd_service_file",
            ]
        }

        self.build_ui()

    def build_ui(self):
        # Title bar with retro styling
        title_frame = tk.Frame(self.root, bg=BG_DARK, bd=0)
        title_frame.pack(fill="x", pady=(10, 0))

        title_label = tk.Label(
            title_frame,
            text="╔══════════════════════════════════════════════════════════╗\n"
                 "║     ⚡  P I   M O N I T O R   D E P L O Y   T O O L  ⚡ ║\n"
                 "╚══════════════════════════════════════════════════════════╝",
            font=("Courier New", 14, "bold"),
            bg=BG_DARK,
            fg=NEON_PINK,
            justify="center"
        )
        title_label.pack(pady=5)

        # Tab navigation frame with neon border
        self.tabs = tk.Frame(self.root, bg=BG_DARK, bd=0)
        self.tabs.pack(fill="x", padx=20, pady=(15, 10))

        # Add decorative line
        tab_line = tk.Frame(self.tabs, bg=NEON_CYAN, height=2)
        tab_line.pack(fill="x")

        self.content = tk.Frame(self.root, bg=BG_DARK)
        self.content.pack(fill="both", expand=True, padx=20, pady=10)

        self.frames = {}

        tab_names = ["Connection", "Paths", "Provision", "Services", "Logs"]
        self.tab_buttons = {}

        for name in tab_names:
            btn = RetroButton(
                self.tabs,
                text=f"  {name}  ",
                command=lambda n=name: self.show_tab(n),
                bg_color=NEON_CYAN,
                font=("Courier New", 11, "bold"),
                padx=6,
                pady=4,
            )
            btn.pack(side="left", padx=3)
            self.tab_buttons[name] = btn

            frame = tk.Frame(self.content, bg=BG_DARK, bd=2, relief="flat")
            frame.config(highlightbackground=NEON_PURPLE, highlightthickness=1)
            self.frames[name] = frame

        # Add bottom decorative line
        bottom_line = tk.Frame(self.root, bg=NEON_CYAN, height=2)
        bottom_line.pack(fill="x", padx=20)

        self.build_connection_tab()
        self.build_paths_tab()
        self.build_provision_tab()
        self.build_services_tab()
        self.build_logs_tab()

        self.show_tab("Connection")

    def show_tab(self, name):
        for frame in self.frames.values():
            frame.pack_forget()
        self.frames[name].pack(fill="both", expand=True)

        # Update tab button styling
        for tab_name, btn in self.tab_buttons.items():
            if tab_name == name:
                btn.config(
                    bg=BG_LIGHT,
                    fg=NEON_PINK,
                    relief="sunken",
                    bd=1
                )
            else:
                btn.config(
                    bg=BG_DARK,
                    fg=NEON_CYAN,
                    relief="flat",
                    bd=0
                )

    def build_connection_tab(self):
        f = self.frames["Connection"]

        # Section header with neon underline
        RetroLabel(f, text="► CONNECTION SETTINGS", font_size=16, color=NEON_PINK).pack(anchor="w", padx=15, pady=(15, 10))
        
        tk.Frame(f, bg=NEON_PINK, height=1).pack(fill="x", padx=15, pady=(0, 15))

        form = tk.Frame(f, bg=BG_DARK)
        form.pack(anchor="w", padx=20)

        RetroLabel(form, text="Pi IP Address:", font_size=11, color=NEON_CYAN).grid(row=0, column=0, sticky="w", pady=8)
        RetroEntry(form, textvariable=self.pi_ip, width=40).grid(row=0, column=1, pady=8, padx=10)

        RetroLabel(form, text="Username:", font_size=11, color=NEON_CYAN).grid(row=1, column=0, sticky="w", pady=8)
        RetroEntry(form, textvariable=self.username, width=40).grid(row=1, column=1, pady=8, padx=10)

        RetroLabel(form, text="Password:", font_size=11, color=NEON_CYAN).grid(row=2, column=0, sticky="w", pady=8)
        RetroEntry(form, textvariable=self.password, show="*", width=40).grid(row=2, column=1, pady=8, padx=10)

        # Save password checkbox
        save_pass_frame = tk.Frame(f, bg=BG_DARK)
        save_pass_frame.pack(anchor="w", padx=20, pady=5)
        
        save_check = RetroCheckbutton(
            save_pass_frame,
            text="Save password",
            variable=self.save_password,
            cursor="hand2"
        )
        save_check.pack(anchor="w")

        btn_frame = tk.Frame(f, bg=BG_DARK)
        btn_frame.pack(anchor="w", padx=20, pady=20)

        RetroButton(btn_frame, text="◄ TEST CONNECTION ►", bg_color=NEON_GREEN, command=lambda: self.threaded(self.test_connection)).pack(side="left")

    def build_paths_tab(self):
        f = self.frames["Paths"]

        RetroLabel(f, text="► DEPLOYMENT PATHS", font_size=16, color=NEON_PINK).pack(anchor="w", padx=15, pady=(15, 10))
        tk.Frame(f, bg=NEON_PINK, height=1).pack(fill="x", padx=15, pady=(0, 15))

        rows = tk.Frame(f, bg=BG_DARK)
        rows.pack(fill="x", padx=20)

        self.add_path_row(rows, 0, "Hardware Script", "hardware_script")
        self.add_path_row(rows, 1, "Docker Compose", "docker_compose")
        self.add_path_row(rows, 2, "Glance Config Folder", "glance_config_folder", select_folder=True)
        self.add_path_row(rows, 3, "Glance Assets Folder", "glance_assets_folder", select_folder=True)
        self.add_path_row(rows, 4, "Kuma Backup Folder", "kuma_backup_folder", select_folder=True)
        self.add_path_row(rows, 5, "Systemd Service File", "systemd_service_file")

        btn_frame = tk.Frame(f, bg=BG_DARK)
        btn_frame.pack(anchor="w", padx=20, pady=20)

        RetroButton(btn_frame, text="◄ SAVE PATHS ►", bg_color=NEON_GREEN, command=self.save_settings).pack(side="left")

    def add_path_row(self, parent, row, label, key, select_folder=False):
        RetroLabel(parent, text=label + ":", font_size=11, color=NEON_CYAN).grid(row=row, column=0, sticky="w", pady=10)
        RetroEntry(parent, textvariable=self.path_vars[key], width=55).grid(row=row, column=1, sticky="ew", pady=10, padx=10)

        # Button frame for Select and View buttons
        btn_frame = tk.Frame(parent, bg=BG_DARK)
        btn_frame.grid(row=row, column=2, padx=5, pady=10)

        def choose():
            selected = filedialog.askdirectory() if select_folder else filedialog.askopenfilename()
            if selected:
                self.path_vars[key].set(selected)

        def view_path():
            path = self.path_vars[key].get()
            if path and os.path.exists(path):
                os.startfile(path)
            else:
                path_type = "Folder" if select_folder else "File"
                self.log(f"► {path_type} not found: {path}")

        RetroButton(btn_frame, text="Select", bg_color=NEON_YELLOW, command=choose, padx=8).pack(side="left", padx=2)
        RetroButton(btn_frame, text="View", bg_color=NEON_PURPLE, command=view_path, padx=8).pack(side="left", padx=2)

    def build_provision_tab(self):
        f = self.frames["Provision"]

        RetroLabel(f, text="► PROVISION EVERYTHING", font_size=16, color=NEON_PINK).pack(anchor="w", padx=15, pady=(15, 10))
        tk.Frame(f, bg=NEON_PINK, height=1).pack(fill="x", padx=15, pady=(0, 15))

        info_text = tk.Label(
            f,
            text="▸ Install dependencies, Docker, Docker apps\n"
                 "▸ Hardware monitor, systemd service\n"
                 "▸ Reboot schedule, Glance YAMLs",
            font=("Courier New", 10),
            bg=BG_DARK,
            fg=NEON_YELLOW,
            justify="left"
        )
        info_text.pack(anchor="w", padx=20, pady=10)

        # Big provision button
        btn_frame = tk.Frame(f, bg=BG_DARK)
        btn_frame.pack(anchor="w", padx=20, pady=20)

        RetroButton(
            btn_frame,
            text="⚡ PROVISION EVERYTHING ⚡",
            bg_color=NEON_ORANGE,
            command=lambda: self.threaded(self.provision_everything)
        ).config(font=("Courier New", 12, "bold"), height=2, width=30)

        # Output log section in Provision tab
        log_label = RetroLabel(f, text="► OUTPUT LOG", font_size=14, color=NEON_CYAN)
        log_label.pack(anchor="w", padx=15, pady=(25, 10))
        
        tk.Frame(f, bg=NEON_CYAN, height=1).pack(fill="x", padx=15, pady=(0, 10))

        # Scrolled text widget for output
        self.provision_log = scrolledtext.ScrolledText(
            f,
            height=12,
            bg=BG_LIGHT,
            fg=NEON_GREEN,
            insertbackground=NEON_PINK,
            font=("Courier New", 9),
            relief="flat",
            bd=2,
        )
        self.provision_log.pack(fill="both", expand=True, padx=20, pady=10)
        self.provision_log.config(state="disabled")

        # Clear button for provision log
        RetroButton(
            f,
            text="◄ CLEAR OUTPUT ►",
            bg_color=NEON_PURPLE,
            command=lambda: self.clear_provision_log()
        ).pack(anchor="w", padx=20, pady=(0, 15))

    def build_services_tab(self):
        f = self.frames["Services"]

        service_body = self.add_collapsible_section(f, "SERVICE CONTROLS", font_size=16, start_open=True)

        buttons = [
            ("► START DOCKER STACK", "cd /srv/docker/compose/core && docker compose up -d"),
            ("■ STOP DOCKER STACK", "cd /srv/docker/compose/core && docker compose down"),
            ("↻ RESTART DOCKER STACK", "cd /srv/docker/compose/core && docker compose restart"),
            ("↻ RESTART GLANCE", "cd /srv/docker/compose/core && docker compose restart glance"),
            ("↻ RESTART HARDWARE MONITOR", "sudo systemctl restart pi-panel.service"),
            ("▣ VIEW HARDWARE MONITOR STATUS", "systemctl status pi-panel.service --no-pager"),
            ("▢ VIEW DOCKER CONTAINERS", "docker ps"),
        ]

        colors = [NEON_GREEN, NEON_ORANGE, NEON_YELLOW, NEON_YELLOW, NEON_CYAN, NEON_CYAN, NEON_CYAN]

        service_grid = tk.Frame(service_body, bg=BG_DARK)
        service_grid.pack(anchor="w", padx=20, pady=5)
        service_grid.columnconfigure(0, weight=1)
        service_grid.columnconfigure(1, weight=1)

        for index, ((text, cmd), color) in enumerate(zip(buttons, colors)):
            btn = RetroButton(service_grid, text=text, bg_color=color, command=lambda c=cmd: self.threaded(lambda: self.run_single_command(c)))
            btn.config(width=34)
            btn.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 15), pady=6)

        deploy_body = self.add_collapsible_section(f, "DEPLOY SELECTED FILES", font_size=14, start_open=True)

        deploy_buttons = [
            ("↻ REPLACE DOCKER COMPOSE", lambda: self.threaded(self.replace_docker_compose), NEON_ORANGE),
            ("↑ IMPORT GLANCE CONFIG", lambda: self.threaded(self.import_glance_config), NEON_CYAN),
            ("↻ REPLACE GLANCE CONFIG", self.confirm_replace_glance_config, NEON_ORANGE),
            ("↑ ADD GLANCE ASSETS", lambda: self.threaded(self.add_glance_assets), NEON_CYAN),
        ]

        deploy_grid = tk.Frame(deploy_body, bg=BG_DARK)
        deploy_grid.pack(anchor="w", padx=20, pady=5)
        deploy_grid.columnconfigure(0, weight=1)
        deploy_grid.columnconfigure(1, weight=1)

        for index, (text, command, color) in enumerate(deploy_buttons):
            btn = RetroButton(deploy_grid, text=text, bg_color=color, command=command)
            btn.config(width=34)
            btn.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 15), pady=6)

        kuma_body = self.add_collapsible_section(f, "KUMA DATA BACKUP", font_size=14, start_open=True)

        kuma_buttons = [
            ("↓ BACKUP KUMA DATA", self.confirm_backup_kuma_data, NEON_GREEN),
            ("↻ RESTORE KUMA DATA", self.confirm_restore_kuma_data, NEON_ORANGE),
        ]

        kuma_grid = tk.Frame(kuma_body, bg=BG_DARK)
        kuma_grid.pack(anchor="w", padx=20, pady=5)
        kuma_grid.columnconfigure(0, weight=1)
        kuma_grid.columnconfigure(1, weight=1)

        for index, (text, command, color) in enumerate(kuma_buttons):
            btn = RetroButton(kuma_grid, text=text, bg_color=color, command=command)
            btn.config(width=34)
            btn.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 15), pady=6)

    def add_collapsible_section(self, parent, title, font_size=14, start_open=True):
        section = tk.Frame(parent, bg=BG_DARK)
        section.pack(fill="x", padx=15, pady=(15, 0))

        body = tk.Frame(section, bg=BG_DARK)
        expanded = tk.BooleanVar(value=start_open)

        header = RetroButton(
            section,
            text=("▼ " if start_open else "► ") + title,
            bg_color=NEON_PINK,
            font=("Courier New", font_size, "bold"),
            anchor="w",
            padx=0,
            pady=0,
        )
        header.pack(fill="x", anchor="w")
        tk.Frame(section, bg=NEON_PINK, height=1).pack(fill="x", pady=(5, 10))

        def toggle():
            if expanded.get():
                body.pack_forget()
                expanded.set(False)
                header.config(text="► " + title)
            else:
                body.pack(fill="x")
                expanded.set(True)
                header.config(text="▼ " + title)

        header.config(command=toggle)

        if start_open:
            body.pack(fill="x")

        return body

    def build_logs_tab(self):
        f = self.frames["Logs"]

        RetroLabel(f, text="► SYSTEM LOGS", font_size=16, color=NEON_PINK).pack(anchor="w", padx=15, pady=(15, 10))
        tk.Frame(f, bg=NEON_PINK, height=1).pack(fill="x", padx=15, pady=(0, 15))

        self.log_box = scrolledtext.ScrolledText(
            f,
            height=28,
            bg=BG_LIGHT,
            fg=NEON_GREEN,
            insertbackground=NEON_PINK,
            font=("Courier New", 9),
            relief="flat",
            bd=2,
        )
        self.log_box.pack(fill="both", expand=True, padx=20, pady=10)

        RetroButton(f, text="◄ CLEAR LOGS ►", bg_color=NEON_PURPLE, command=lambda: self.log_box.delete("1.0", tk.END)).pack(anchor="w", padx=20, pady=(0, 10))

    def log(self, text):
        self.show_tab("Logs")
        self.log_box.insert(tk.END, str(text) + "\n")
        self.log_box.see(tk.END)
        self.root.update_idletasks()

    def provision_log_write(self, text):
        """Write to the provision tab's output log"""
        self.provision_log.config(state="normal")
        self.provision_log.insert(tk.END, str(text) + "\n")
        self.provision_log.see(tk.END)
        self.provision_log.config(state="disabled")
        self.root.update_idletasks()

    def clear_provision_log(self):
        """Clear the provision tab's output log"""
        self.provision_log.config(state="normal")
        self.provision_log.delete("1.0", tk.END)
        self.provision_log.config(state="disabled")

    def threaded(self, target):
        t = threading.Thread(target=target, daemon=True)
        t.start()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                self.settings.update(json.load(f))

    def save_settings(self):
        self.settings["pi_ip"] = self.pi_ip.get()
        self.settings["username"] = self.username.get()
        self.settings["save_password"] = self.save_password.get()
        
        # Only save password if checkbox is checked
        if self.save_password.get():
            self.settings["password"] = self.password.get()
        else:
            self.settings["password"] = ""

        for key, var in self.path_vars.items():
            self.settings[key] = var.get()

        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2)

        self.log("► Settings saved.")

    def connect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=self.pi_ip.get(),
            username=self.username.get(),
            password=self.password.get(),
            timeout=20,
        )
        return ssh

    def run(self, ssh, command, sudo_password=False):
        self.log(f"$ {command}")
        self.provision_log_write(f"$ {command}")

        stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)

        if sudo_password:
            stdin.write(self.password.get() + "\n")
            stdin.flush()

        for line in stdout:
            self.log(line.rstrip())
            self.provision_log_write(line.rstrip())

        err = stderr.read().decode(errors="ignore").strip()
        if err:
            self.log(err)
            self.provision_log_write(err)

        code = stdout.channel.recv_exit_status()
        if code != 0:
            raise RuntimeError(f"Command failed: {command}")

    def upload_file(self, ssh, local_file, remote_file):
        self.log(f"Uploading file: {local_file} -> {remote_file}")
        self.provision_log_write(f"↑ Uploading: {os.path.basename(local_file)}")

        remote_dir = os.path.dirname(remote_file)
        self.prepare_remote_upload_folder(ssh, remote_dir)

        with SCPClient(ssh.get_transport()) as scp:
            scp.put(local_file, remote_file)

    def upload_folder_contents(self, ssh, local_folder, remote_folder):
        self.log(f"Uploading folder contents: {local_folder} -> {remote_folder}")
        self.provision_log_write(f"↑ Uploading folder: {os.path.basename(local_folder)}")

        self.prepare_remote_upload_folder(ssh, remote_folder)

        with SCPClient(ssh.get_transport()) as scp:
            for item in os.listdir(local_folder):
                src = os.path.join(local_folder, item)
                scp.put(src, remote_path=remote_folder, recursive=True)

    def prepare_remote_upload_folder(self, ssh, remote_folder):
        user = self.username.get()
        self.run(ssh, f"sudo mkdir -p {remote_folder}", sudo_password=True)
        self.run(ssh, f"sudo chown -R {user}:{user} {remote_folder}", sudo_password=True)

    def download_folder_contents(self, ssh, remote_folder, local_folder):
        self.log(f"Downloading folder contents: {remote_folder} -> {local_folder}")
        self.provision_log_write(f"↓ Downloading folder: {os.path.basename(remote_folder)}")

        os.makedirs(local_folder, exist_ok=True)

        def download_recursive(sftp, remote_path, local_path):
            os.makedirs(local_path, exist_ok=True)
            for item in sftp.listdir_attr(remote_path):
                remote_item = remote_path.rstrip("/") + "/" + item.filename
                local_item = os.path.join(local_path, item.filename)

                if stat.S_ISDIR(item.st_mode):
                    download_recursive(sftp, remote_item, local_item)
                else:
                    sftp.get(remote_item, local_item)

        with ssh.open_sftp() as sftp:
            download_recursive(sftp, remote_folder, local_folder)

    def validate_paths(self):
        required = {
            "hardware_script": "Hardware script",
            "docker_compose": "Docker compose",
            "glance_config_folder": "Glance config folder",
            "systemd_service_file": "Systemd service file",
        }

        for key, label in required.items():
            path = self.path_vars[key].get()
            if not path or not os.path.exists(path):
                raise FileNotFoundError(f"Missing or invalid path: {label}")

    def require_file_path(self, key, label):
        path = self.path_vars[key].get()
        if not path or not os.path.isfile(path):
            raise FileNotFoundError(f"Missing or invalid file: {label}")
        return path

    def require_folder_path(self, key, label):
        path = self.path_vars[key].get()
        if not path or not os.path.isdir(path):
            raise FileNotFoundError(f"Missing or invalid folder: {label}")
        return path

    def test_connection(self):
        try:
            # Auto-save if save password is checked
            if self.save_password.get():
                self.save_settings()
            
            self.show_tab("Logs")
            self.log("► Testing connection...")
            ssh = self.connect()
            self.run(ssh, "hostname && whoami")
            ssh.close()
            self.log("► Connection successful!")
        except Exception as e:
            self.log(f"ERROR: {e}")

    def provision_everything(self):
        try:
            # Auto-save if save password is checked
            if self.save_password.get():
                self.save_settings()
            
            self.show_tab("Provision")
            self.clear_provision_log()
            self.provision_log_write("⚡ STARTING PROVISION... ⚡")
            self.provision_log_write("=" * 50)
            
            self.validate_paths()

            ssh = self.connect()

            user = self.username.get()

            self.run(ssh, "sudo apt update && sudo apt upgrade -y", sudo_password=True)
            self.run(ssh, "sudo apt install -y curl git python3 python3-pip python3-venv i2c-tools", sudo_password=True)

            self.run(ssh, "if command -v docker >/dev/null 2>&1; then echo Docker already installed; else curl -fsSL https://get.docker.com | sh; fi")
            self.run(ssh, "sudo apt install -y docker-compose-plugin", sudo_password=True)
            self.run(ssh, "sudo systemctl enable docker && sudo systemctl start docker", sudo_password=True)
            self.run(ssh, f"sudo usermod -aG docker {user}", sudo_password=True)

            self.run(ssh, "sudo mkdir -p /srv/docker/compose/core /srv/docker/data/kuma /srv/docker/data/glance/config /srv/docker/data/glance/assets", sudo_password=True)
            self.run(ssh, f"sudo mkdir -p {REMOTE_HARDWARE_DIR}", sudo_password=True)
            self.run(ssh, f"sudo chown -R {user}:{user} /srv/docker {REMOTE_HARDWARE_DIR}", sudo_password=True)

            self.upload_file(ssh, self.path_vars["docker_compose"].get(), f"{REMOTE_DOCKER_DIR}/docker-compose.yml")
            self.upload_file(ssh, self.path_vars["hardware_script"].get(), f"{REMOTE_HARDWARE_DIR}/pi_assembly.py")
            self.upload_file(ssh, self.path_vars["systemd_service_file"].get(), "/tmp/pi-panel.service")

            self.run(ssh, "sudo cp /tmp/pi-panel.service /etc/systemd/system/pi-panel.service", sudo_password=True)
            self.run(ssh, "sudo chmod +x /srv/samba/share/pi_housing_code/pi_assembly.py", sudo_password=True)

            self.upload_folder_contents(ssh, self.path_vars["glance_config_folder"].get(), REMOTE_GLANCE_CONFIG)

            assets_path = self.path_vars["glance_assets_folder"].get()
            if assets_path and os.path.exists(assets_path):
                self.upload_folder_contents(ssh, assets_path, REMOTE_GLANCE_ASSETS)

            self.run(ssh, "sudo systemctl daemon-reload", sudo_password=True)
            self.run(ssh, "sudo systemctl enable pi-panel.service", sudo_password=True)
            self.run(ssh, "sudo systemctl restart pi-panel.service", sudo_password=True)

            self.run(
                ssh,
                "(sudo crontab -l 2>/dev/null | grep -v '/sbin/reboot'; echo '0 3 * * 0 /sbin/reboot') | sudo crontab -",
                sudo_password=True
            )

            self.run(ssh, "cd /srv/docker/compose/core && docker compose up -d")

            ssh.close()
            
            self.provision_log_write("=" * 50)
            self.provision_log_write("⚡ PROVISION COMPLETED! ⚡")
        except Exception as e:
            self.provision_log_write(f"ERROR: {e}")
            self.log(f"ERROR: {e}")

    def run_single_command(self, command):
        try:
            ssh = self.connect()
            self.run(ssh, command, sudo_password=command.strip().startswith("sudo"))
            ssh.close()
        except Exception as e:
            self.log(f"ERROR: {e}")

    def replace_docker_compose(self):
        try:
            compose_path = self.require_file_path("docker_compose", "Docker compose")
            ssh = self.connect()
            self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose down")
            self.upload_file(ssh, compose_path, f"{REMOTE_DOCKER_DIR}/docker-compose.yml")
            self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose up -d")
            ssh.close()
            self.log("► Docker compose replaced and stack restarted.")
        except Exception as e:
            self.log(f"ERROR: {e}")

    def import_glance_config(self):
        try:
            config_path = self.require_folder_path("glance_config_folder", "Glance config folder")
            ssh = self.connect()
            self.upload_folder_contents(ssh, config_path, REMOTE_GLANCE_CONFIG)
            self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose restart glance")
            ssh.close()
            self.log("► Glance config imported and Glance restarted.")
        except Exception as e:
            self.log(f"ERROR: {e}")

    def replace_glance_config(self):
        try:
            config_path = self.require_folder_path("glance_config_folder", "Glance config folder")
            ssh = self.connect()
            self.run(ssh, f"mkdir -p {REMOTE_GLANCE_CONFIG}")
            self.run(ssh, f"find {REMOTE_GLANCE_CONFIG} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} +")
            self.upload_folder_contents(ssh, config_path, REMOTE_GLANCE_CONFIG)
            self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose restart glance")
            ssh.close()
            self.log("► Glance config replaced and Glance restarted.")
        except Exception as e:
            self.log(f"ERROR: {e}")

    def confirm_replace_glance_config(self):
        confirmed = messagebox.askyesno(
            "Replace Glance Config",
            "This will remove the existing remote Glance config contents before uploading the selected folder. Continue?"
        )
        if confirmed:
            self.threaded(self.replace_glance_config)
        else:
            self.log("► Replace Glance config cancelled.")

    def add_glance_assets(self):
        try:
            assets_path = self.require_folder_path("glance_assets_folder", "Glance assets folder")
            ssh = self.connect()
            self.upload_folder_contents(ssh, assets_path, REMOTE_GLANCE_ASSETS)
            self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose restart glance")
            ssh.close()
            self.log("► Glance assets added and Glance restarted.")
        except Exception as e:
            self.log(f"ERROR: {e}")

    def confirm_backup_kuma_data(self):
        confirmed = messagebox.askyesno(
            "Backup Kuma Data",
            "This will stop the Docker stack, copy the remote Kuma data folder into a timestamped local backup folder, then start the stack again. Continue?"
        )
        if confirmed:
            self.threaded(self.backup_kuma_data)
        else:
            self.log("► Kuma backup cancelled.")

    def backup_kuma_data(self):
        ssh = None
        stack_stopped = False

        try:
            backup_root = self.require_folder_path("kuma_backup_folder", "Kuma backup folder")
            backup_name = "kuma_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_root, backup_name)

            ssh = self.connect()
            self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose down")
            stack_stopped = True
            self.download_folder_contents(ssh, REMOTE_KUMA_DATA, backup_path)
            self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose up -d")
            stack_stopped = False
            ssh.close()
            self.log(f"► Kuma data backed up to: {backup_path}")
        except Exception as e:
            self.log(f"ERROR: {e}")
            if ssh and stack_stopped:
                try:
                    self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose up -d")
                except Exception as restart_error:
                    self.log(f"ERROR restarting Docker stack: {restart_error}")
            if ssh:
                ssh.close()

    def confirm_restore_kuma_data(self):
        confirmed = messagebox.askyesno(
            "Restore Kuma Data",
            "This will stop the Docker stack and replace the remote Kuma data folder contents with the selected Kuma backup folder. Continue?"
        )
        if confirmed:
            self.threaded(self.restore_kuma_data)
        else:
            self.log("► Kuma restore cancelled.")

    def restore_kuma_data(self):
        ssh = None
        stack_stopped = False

        try:
            backup_path = self.require_folder_path("kuma_backup_folder", "Kuma backup folder")
            ssh = self.connect()
            self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose down")
            stack_stopped = True
            self.run(ssh, f"mkdir -p {REMOTE_KUMA_DATA}")
            self.run(ssh, f"find {REMOTE_KUMA_DATA} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} +")
            self.upload_folder_contents(ssh, backup_path, REMOTE_KUMA_DATA)
            self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose up -d")
            stack_stopped = False
            ssh.close()
            self.log("► Kuma data restored and Docker stack restarted.")
        except Exception as e:
            self.log(f"ERROR: {e}")
            if ssh and stack_stopped:
                try:
                    self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose up -d")
                except Exception as restart_error:
                    self.log(f"ERROR restarting Docker stack: {restart_error}")
            if ssh:
                ssh.close()


if __name__ == "__main__":
    root = tk.Tk()
    app = PiDeployTool(root)
    root.mainloop()
