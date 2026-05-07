import json
import os
import re
import shlex
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
NEON_RED = "#ff3131"
TEXT_WHITE = "#ffffff"
TEXT_GRAY = "#888888"


APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(APP_DIR, "deploy_tool_settings.json")
WEBSITE_PATHS_FILE = os.path.join(APP_DIR, "website_paths.json")
DISCORD_BOT_PATHS_FILE = os.path.join(APP_DIR, "discord_bot_paths.json")

REMOTE_BASE = "/srv/pi-monitor-deploy"
REMOTE_HARDWARE_DIR = "/srv/samba/share/pi_housing_code"
REMOTE_DOCKER_DIR = "/srv/docker/compose/core"
REMOTE_GLANCE_CONFIG = "/srv/docker/data/glance/config"
REMOTE_GLANCE_ASSETS = "/srv/docker/data/glance/assets"
REMOTE_KUMA_DATA = "/srv/docker/data/kuma"
REMOTE_WEBSITES_DIR = "/srv/docker/data/websites"
REMOTE_DISCORD_BOTS_DIR = "/srv/docker/data/discord-bots"


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
            highlightbackground=self.accent,
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
        super().configure(bg=self.normal_bg, highlightbackground=self.accent)
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
            frame_options["highlightbackground"] = self.accent
        if "bg_color" in options:
            self.accent = options.pop("bg_color")
            label_options["fg"] = self.accent
            frame_options["highlightcolor"] = self.accent
            frame_options["highlightbackground"] = self.accent
        if "bg" in options:
            self.normal_bg = options.pop("bg")
            frame_options["bg"] = self.normal_bg
            frame_options["highlightbackground"] = self.accent
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
        self.website_paths = self.load_website_paths()
        self.discord_bot_paths = self.load_discord_bot_paths()
        self.website_status_labels = {}
        self.discord_bot_status_labels = {}
        self.scroll_canvases = {}
        self.current_tab = None

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

        tab_names = ["Connection", "Paths", "Provision", "Services", "Website Control Panel", "Discord Bot Control", "Logs"]
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
        self.build_website_control_tab()
        self.build_discord_bot_control_tab()
        self.build_logs_tab()

        self.show_tab("Connection")
        self.root.bind_all("<MouseWheel>", self.on_global_mousewheel)
        self.root.bind_all("<Button-4>", self.on_global_mousewheel)
        self.root.bind_all("<Button-5>", self.on_global_mousewheel)

    def show_tab(self, name):
        self.current_tab = name
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

    def on_global_mousewheel(self, event):
        canvas = self.scroll_canvases.get(self.current_tab)
        if not canvas:
            return
        if not self.canvas_can_scroll(canvas):
            canvas.yview_moveto(0)
            return "break"

        delta = getattr(event, "delta", 0)
        if delta:
            units = int(-delta / 120)
            if units == 0:
                units = -1 if delta > 0 else 1
            canvas.yview_scroll(units, "units")
        elif getattr(event, "num", None) == 4:
            canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            canvas.yview_scroll(1, "units")

        return "break"

    def canvas_can_scroll(self, canvas):
        bbox = canvas.bbox("all")
        if not bbox:
            return False
        content_height = bbox[3] - bbox[1]
        return content_height > canvas.winfo_height() + 1

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

    def create_scroll_area(self, parent, body_attr=None, padx=(0, 4), pady=(0, 10), scrollbar_padx=(0, 0)):
        canvas = tk.Canvas(parent, bg=BG_DARK, highlightthickness=0)
        scrollbar_slot = tk.Frame(parent, bg=BG_DARK, width=14)
        scrollbar_slot.pack_propagate(False)
        scrollbar = tk.Scrollbar(
            scrollbar_slot,
            orient="vertical",
            command=canvas.yview,
            bg=BG_LIGHT,
            troughcolor=BG_DARK,
            activebackground=NEON_PINK,
            highlightthickness=1,
            highlightbackground=NEON_CYAN,
            relief="flat",
            bd=0,
            width=14,
        )
        scroll_body = tk.Frame(canvas, bg=BG_DARK)
        scroll_window = canvas.create_window((0, 0), window=scroll_body, anchor="nw")
        wheel_remainder = {"value": 0.0}
        scrollbar_visible = {"value": False}

        def set_scrollbar_visible(visible):
            if visible == scrollbar_visible["value"]:
                return
            scrollbar_visible["value"] = visible
            if visible:
                scrollbar.pack(fill="y", expand=True)
            else:
                scrollbar.pack_forget()

        def update_scroll_region(_event=None):
            bbox = canvas.bbox("all")
            if not bbox:
                canvas.configure(scrollregion=(0, 0, 0, canvas.winfo_height()))
                set_scrollbar_visible(False)
                return
            canvas_height = canvas.winfo_height()
            content_height = bbox[3] - bbox[1]
            bottom = max(bbox[3], bbox[1] + canvas_height)
            canvas.configure(scrollregion=(bbox[0], bbox[1], bbox[2], bottom))
            can_scroll = content_height > canvas_height + 1
            set_scrollbar_visible(can_scroll)
            if not can_scroll:
                canvas.yview_moveto(0)

        def resize_scroll_body(event):
            canvas.itemconfigure(scroll_window, width=event.width)
            update_scroll_region()

        def on_mousewheel(event):
            if not self.canvas_can_scroll(canvas):
                canvas.yview_moveto(0)
                return "break"

            delta = getattr(event, "delta", 0)
            if delta:
                wheel_remainder["value"] += -delta / 120
                units = int(wheel_remainder["value"])
                if units == 0:
                    units = -1 if delta > 0 else 1
                wheel_remainder["value"] -= units
                canvas.yview_scroll(units, "units")
            elif getattr(event, "num", None) == 4:
                canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(1, "units")

            return "break"

        scroll_body.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_scroll_body)
        canvas.bind("<MouseWheel>", on_mousewheel)
        canvas.bind("<Button-4>", on_mousewheel)
        canvas.bind("<Button-5>", on_mousewheel)
        scroll_body.bind("<MouseWheel>", on_mousewheel)
        scroll_body.bind("<Button-4>", on_mousewheel)
        scroll_body.bind("<Button-5>", on_mousewheel)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=padx, pady=pady)
        scrollbar_slot.pack(side="right", fill="y", padx=scrollbar_padx, pady=pady)

        if body_attr:
            setattr(self, body_attr, scroll_body)

        return scroll_body, canvas, scrollbar

    def build_paths_tab(self):
        f = self.frames["Paths"]

        scroll_body, canvas, _scrollbar = self.create_scroll_area(f)
        self.scroll_canvases["Paths"] = canvas

        deployment_body = self.add_collapsible_section(scroll_body, "DEPLOYMENT PATHS", font_size=16, start_open=True)

        rows = tk.Frame(deployment_body, bg=BG_DARK)
        rows.pack(fill="x", padx=20)

        self.add_path_row(rows, 0, "Hardware Script", "hardware_script")
        self.add_path_row(rows, 1, "Docker Compose", "docker_compose")
        self.add_path_row(rows, 2, "Glance Config Folder", "glance_config_folder", select_folder=True)
        self.add_path_row(rows, 3, "Glance Assets Folder", "glance_assets_folder", select_folder=True)
        self.add_path_row(rows, 4, "Kuma Backup Folder", "kuma_backup_folder", select_folder=True)
        self.add_path_row(rows, 5, "Systemd Service File", "systemd_service_file")

        btn_frame = tk.Frame(deployment_body, bg=BG_DARK)
        btn_frame.pack(anchor="w", padx=20, pady=20)

        RetroButton(btn_frame, text="◄ SAVE PATHS ►", bg_color=NEON_GREEN, command=self.save_settings).pack(side="left")

        website_body = self.add_collapsible_section(scroll_body, "WEBSITE PATHS", font_size=14, start_open=True)
        website_header = tk.Frame(website_body, bg=BG_DARK)
        website_header.pack(fill="x", padx=20, pady=(5, 10))

        RetroLabel(
            website_header,
            text="Add local website folders for upload and hosting controls.",
            font_size=10,
            color=NEON_YELLOW,
        ).pack(side="left", anchor="w")

        RetroButton(
            website_header,
            text="+",
            bg_color=NEON_GREEN,
            command=self.add_website_path_dialog,
            width=3,
            padx=4,
        ).pack(side="right", padx=5)

        self.website_paths_list = tk.Frame(website_body, bg=BG_DARK)
        self.website_paths_list.pack(fill="x", padx=20, pady=(0, 10))
        self.refresh_website_paths_list()

        bot_body = self.add_collapsible_section(scroll_body, "DISCORD BOT PATHS", font_size=14, start_open=True)
        bot_header = tk.Frame(bot_body, bg=BG_DARK)
        bot_header.pack(fill="x", padx=20, pady=(5, 10))

        RetroLabel(
            bot_header,
            text="Add local Discord bot folders for upload and background Node controls.",
            font_size=10,
            color=NEON_YELLOW,
        ).pack(side="left", anchor="w")

        RetroButton(
            bot_header,
            text="+",
            bg_color=NEON_GREEN,
            command=self.add_discord_bot_path_dialog,
            width=3,
            padx=4,
        ).pack(side="right", padx=5)

        self.discord_bot_paths_list = tk.Frame(bot_body, bg=BG_DARK)
        self.discord_bot_paths_list.pack(fill="x", padx=20, pady=(0, 10))
        self.refresh_discord_bot_paths_list()

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

    def slugify_site_name(self, name):
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug or "website"

    def detect_node_port(self, node_file):
        try:
            with open(node_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            return ""

        match = re.search(r"\bPORT\s*=\s*(\d+)", content)
        return match.group(1) if match else ""

    def normalize_deployables(self, site):
        site_slug = site["service_name"]
        deployables = site.get("deployables")
        if not isinstance(deployables, list) or not deployables:
            deployables = [{
                "name": "site",
                "file": "app.js",
                "service_name": site_slug,
                "host_port": 8088,
                "container_port": 3000,
            }]

        normalized = []
        for index, deployable in enumerate(deployables):
            if not isinstance(deployable, dict):
                continue
            label = str(deployable.get("name", "")).strip() or f"service-{index + 1}"
            node_file = str(deployable.get("file", "")).strip() or "app.js"
            service_name = str(deployable.get("service_name", "")).strip()
            if not service_name:
                service_name = f"{site_slug}-{self.slugify_site_name(label)}"
            host_port = str(deployable.get("host_port", "")).strip() or str(8088 + index)
            container_port = str(deployable.get("container_port", "")).strip()
            full_node_file = os.path.join(site["path"], node_file)
            detected_port = self.detect_node_port(full_node_file)
            if detected_port and (not container_port or container_port == host_port):
                container_port = detected_port
            if not container_port:
                container_port = host_port

            normalized.append({
                "name": label,
                "file": node_file,
                "service_name": service_name,
                "host_port": int(host_port),
                "container_port": int(container_port),
            })

        return normalized

    def load_website_paths(self):
        if not os.path.exists(WEBSITE_PATHS_FILE):
            return []

        try:
            with open(WEBSITE_PATHS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(data, list):
            return []

        websites = []
        for site in data:
            if not isinstance(site, dict):
                continue
            name = str(site.get("name", "")).strip()
            path = str(site.get("path", "")).strip()
            if not name or not path:
                continue
            service_name = str(site.get("service_name", "")).strip() or self.slugify_site_name(name)
            normalized = {"name": name, "path": path, "service_name": service_name}
            normalized["deployables"] = self.normalize_deployables({**site, **normalized})
            websites.append(normalized)
        return websites

    def save_website_paths(self):
        with open(WEBSITE_PATHS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.website_paths, f, indent=2)

    def normalize_discord_bot_entries(self, bot):
        bot_slug = bot["service_name"]
        entries = bot.get("entries")
        if not isinstance(entries, list) or not entries:
            entries = [{
                "name": "bot",
                "file": "index.js",
                "service_name": bot_slug,
            }]

        normalized = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("name", "")).strip() or f"bot-{index + 1}"
            node_file = str(entry.get("file", "")).strip() or "index.js"
            service_name = str(entry.get("service_name", "")).strip()
            if not service_name:
                service_name = f"{bot_slug}-{self.slugify_site_name(label)}"

            normalized.append({
                "name": label,
                "file": node_file,
                "service_name": service_name,
            })

        return normalized

    def load_discord_bot_paths(self):
        if not os.path.exists(DISCORD_BOT_PATHS_FILE):
            return []

        try:
            with open(DISCORD_BOT_PATHS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

        if not isinstance(data, list):
            return []

        bots = []
        for bot in data:
            if not isinstance(bot, dict):
                continue
            name = str(bot.get("name", "")).strip()
            path = str(bot.get("path", "")).strip()
            if not name or not path:
                continue
            service_name = str(bot.get("service_name", "")).strip() or self.slugify_site_name(name)
            normalized = {"name": name, "path": path, "service_name": service_name}
            normalized["entries"] = self.normalize_discord_bot_entries({**bot, **normalized})
            bots.append(normalized)
        return bots

    def save_discord_bot_paths(self):
        with open(DISCORD_BOT_PATHS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.discord_bot_paths, f, indent=2)

    def add_website_path_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Website Path")
        dialog.configure(bg=BG_DARK)
        dialog.transient(self.root)
        dialog.grab_set()

        name_var = tk.StringVar()
        path_var = tk.StringVar()
        deployable_rows = []

        RetroLabel(dialog, text="Website Name:", font_size=11, color=NEON_CYAN).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 8))
        RetroEntry(dialog, textvariable=name_var, width=42).grid(row=0, column=1, sticky="ew", padx=10, pady=(15, 8))

        RetroLabel(dialog, text="Local Path:", font_size=11, color=NEON_CYAN).grid(row=1, column=0, sticky="w", padx=15, pady=8)
        RetroEntry(dialog, textvariable=path_var, width=42).grid(row=1, column=1, sticky="ew", padx=10, pady=8)

        def choose_path():
            selected = filedialog.askdirectory(parent=dialog)
            if selected:
                path_var.set(selected)

        RetroButton(dialog, text="Select", bg_color=NEON_YELLOW, command=choose_path, padx=8).grid(row=1, column=2, padx=(0, 15), pady=8)

        deployable_header = tk.Frame(dialog, bg=BG_DARK)
        deployable_header.grid(row=2, column=0, columnspan=3, sticky="ew", padx=15, pady=(12, 6))

        RetroLabel(deployable_header, text="Node Serve Files", font_size=12, color=NEON_PINK).pack(side="left")

        deployable_frame = tk.Frame(dialog, bg=BG_DARK)
        deployable_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=15)

        def refresh_deployable_rows():
            for child in deployable_frame.winfo_children():
                child.destroy()

            headers = ["Name", "Node File", "Host Port", "Node Port", ""]
            for col, header in enumerate(headers):
                RetroLabel(deployable_frame, text=header, font_size=9, color=NEON_CYAN).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 4))

            for row_index, row_data in enumerate(deployable_rows, start=1):
                RetroEntry(deployable_frame, textvariable=row_data["name"], width=14).grid(row=row_index, column=0, padx=4, pady=4)
                RetroEntry(deployable_frame, textvariable=row_data["file"], width=24).grid(row=row_index, column=1, padx=4, pady=4)
                RetroEntry(deployable_frame, textvariable=row_data["host_port"], width=8).grid(row=row_index, column=2, padx=4, pady=4)
                RetroEntry(deployable_frame, textvariable=row_data["container_port"], width=8).grid(row=row_index, column=3, padx=4, pady=4)

                def choose_file(data=row_data):
                    base_path = path_var.get().strip()
                    selected = filedialog.askopenfilename(
                        parent=dialog,
                        initialdir=base_path if os.path.isdir(base_path) else None,
                        filetypes=[("Node files", "*.js"), ("All files", "*.*")],
                    )
                    if selected:
                        if base_path and selected.startswith(base_path):
                            selected = os.path.relpath(selected, base_path)
                        data["file"].set(selected.replace("\\", "/"))
                        detected_port = self.detect_node_port(os.path.join(base_path, selected))
                        if detected_port:
                            data["container_port"].set(detected_port)

                RetroButton(deployable_frame, text="File", bg_color=NEON_YELLOW, command=choose_file, padx=6).grid(row=row_index, column=4, padx=4, pady=4)
                RetroButton(deployable_frame, text="-", bg_color=NEON_ORANGE, command=lambda d=row_data: remove_deployable_row(d), width=3, padx=4).grid(row=row_index, column=5, padx=4, pady=4)

        def add_deployable_row(label=None, node_file=None, host_port=None, container_port=None):
            index = len(deployable_rows)
            deployable_rows.append({
                "name": tk.StringVar(value=label or ("site" if index == 0 else f"service-{index + 1}")),
                "file": tk.StringVar(value=node_file or ("app.js" if index == 0 else "")),
                "host_port": tk.StringVar(value=str(host_port or (4000 + index))),
                "container_port": tk.StringVar(value=str(container_port or "")),
            })
            refresh_deployable_rows()

        def remove_deployable_row(row_data):
            if len(deployable_rows) <= 1:
                messagebox.showerror("Deployable Required", "Keep at least one Node serve file.", parent=dialog)
                return
            deployable_rows.remove(row_data)
            refresh_deployable_rows()

        RetroButton(
            deployable_header,
            text="+",
            bg_color=NEON_GREEN,
            command=add_deployable_row,
            width=3,
            padx=4,
        ).pack(side="right")

        add_deployable_row("site", "app.js", 4000, "")

        buttons = tk.Frame(dialog, bg=BG_DARK)
        buttons.grid(row=4, column=0, columnspan=3, sticky="e", padx=15, pady=15)

        def save_site():
            name = name_var.get().strip()
            path = path_var.get().strip()
            if not name:
                messagebox.showerror("Missing Name", "Give the website a name.", parent=dialog)
                return
            if not path or not os.path.isdir(path):
                messagebox.showerror("Missing Path", "Choose an existing website folder.", parent=dialog)
                return

            service_name = self.slugify_site_name(name)
            if any(site["service_name"] == service_name for site in self.website_paths):
                messagebox.showerror("Duplicate Website", f"A website named {service_name} already exists.", parent=dialog)
                return

            deployables = []
            used_services = set()
            for index, row_data in enumerate(deployable_rows):
                label = row_data["name"].get().strip()
                node_file = row_data["file"].get().strip().replace("\\", "/")
                host_port = row_data["host_port"].get().strip()
                container_port = row_data["container_port"].get().strip()
                if not label or not node_file or not host_port:
                    messagebox.showerror("Missing Deployable", "Each serve file needs a name, file, and host port.", parent=dialog)
                    return
                full_node_file = os.path.join(path, node_file)
                if not os.path.isfile(full_node_file):
                    messagebox.showerror("Missing Node File", f"Node file not found: {node_file}", parent=dialog)
                    return
                if not container_port:
                    container_port = self.detect_node_port(full_node_file) or host_port

                deploy_service = f"{service_name}-{self.slugify_site_name(label)}"
                if deploy_service in used_services:
                    messagebox.showerror("Duplicate Deployable", f"Duplicate deployable name: {label}", parent=dialog)
                    return
                used_services.add(deploy_service)

                deployables.append({
                    "name": label,
                    "file": node_file,
                    "service_name": deploy_service,
                    "host_port": int(host_port),
                    "container_port": int(container_port),
                })

            self.website_paths.append({
                "name": name,
                "path": path,
                "service_name": service_name,
                "deployables": deployables,
            })
            self.save_website_paths()
            self.refresh_website_paths_list()
            self.refresh_website_control_panel()
            self.log(f"Website path added: {name}")
            dialog.destroy()

        RetroButton(buttons, text="Cancel", bg_color=NEON_PURPLE, command=dialog.destroy, padx=10).pack(side="right", padx=5)
        RetroButton(buttons, text="Add Website", bg_color=NEON_GREEN, command=save_site, padx=10).pack(side="right", padx=5)

        dialog.columnconfigure(1, weight=1)

    def remove_website_path(self, site):
        confirmed = messagebox.askyesno(
            "Remove Website",
            f"Remove {site['name']} from the website path list?\n\nThis does not delete files from your Pi.",
        )
        if not confirmed:
            return

        self.website_paths = [item for item in self.website_paths if item["service_name"] != site["service_name"]]
        self.save_website_paths()
        self.refresh_website_paths_list()
        self.refresh_website_control_panel()
        self.log(f"Website path removed: {site['name']}")

    def view_website_path(self, site):
        path = site["path"]
        if path and os.path.exists(path):
            os.startfile(path)
        else:
            self.log(f"Website folder not found: {path}")

    def add_discord_bot_path_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Discord Bot Path")
        dialog.configure(bg=BG_DARK)
        dialog.transient(self.root)
        dialog.grab_set()

        name_var = tk.StringVar()
        path_var = tk.StringVar()
        entry_rows = []

        RetroLabel(dialog, text="Bot Name:", font_size=11, color=NEON_CYAN).grid(row=0, column=0, sticky="w", padx=15, pady=(15, 8))
        RetroEntry(dialog, textvariable=name_var, width=42).grid(row=0, column=1, sticky="ew", padx=10, pady=(15, 8))

        RetroLabel(dialog, text="Local Path:", font_size=11, color=NEON_CYAN).grid(row=1, column=0, sticky="w", padx=15, pady=8)
        RetroEntry(dialog, textvariable=path_var, width=42).grid(row=1, column=1, sticky="ew", padx=10, pady=8)

        def choose_path():
            selected = filedialog.askdirectory(parent=dialog)
            if selected:
                path_var.set(selected)

        RetroButton(dialog, text="Select", bg_color=NEON_YELLOW, command=choose_path, padx=8).grid(row=1, column=2, padx=(0, 15), pady=8)

        entry_header = tk.Frame(dialog, bg=BG_DARK)
        entry_header.grid(row=2, column=0, columnspan=3, sticky="ew", padx=15, pady=(12, 6))
        RetroLabel(entry_header, text="Node Entry Files", font_size=12, color=NEON_PINK).pack(side="left")

        entry_frame = tk.Frame(dialog, bg=BG_DARK)
        entry_frame.grid(row=3, column=0, columnspan=3, sticky="ew", padx=15)

        def refresh_entry_rows():
            for child in entry_frame.winfo_children():
                child.destroy()

            headers = ["Name", "Node File", ""]
            for col, header in enumerate(headers):
                RetroLabel(entry_frame, text=header, font_size=9, color=NEON_CYAN).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 4))

            for row_index, row_data in enumerate(entry_rows, start=1):
                RetroEntry(entry_frame, textvariable=row_data["name"], width=18).grid(row=row_index, column=0, padx=4, pady=4)
                RetroEntry(entry_frame, textvariable=row_data["file"], width=32).grid(row=row_index, column=1, padx=4, pady=4)

                def choose_file(data=row_data):
                    base_path = path_var.get().strip()
                    selected = filedialog.askopenfilename(
                        parent=dialog,
                        initialdir=base_path if os.path.isdir(base_path) else None,
                        filetypes=[("Node files", "*.js"), ("All files", "*.*")],
                    )
                    if selected:
                        if base_path and selected.startswith(base_path):
                            selected = os.path.relpath(selected, base_path)
                        data["file"].set(selected.replace("\\", "/"))

                RetroButton(entry_frame, text="File", bg_color=NEON_YELLOW, command=choose_file, padx=6).grid(row=row_index, column=2, padx=4, pady=4)
                RetroButton(entry_frame, text="-", bg_color=NEON_ORANGE, command=lambda d=row_data: remove_entry_row(d), width=3, padx=4).grid(row=row_index, column=3, padx=4, pady=4)

        def add_entry_row(label=None, node_file=None):
            index = len(entry_rows)
            entry_rows.append({
                "name": tk.StringVar(value=label or ("bot" if index == 0 else f"bot-{index + 1}")),
                "file": tk.StringVar(value=node_file or ("index.js" if index == 0 else "")),
            })
            refresh_entry_rows()

        def remove_entry_row(row_data):
            if len(entry_rows) <= 1:
                messagebox.showerror("Entry Required", "Keep at least one Node entry file.", parent=dialog)
                return
            entry_rows.remove(row_data)
            refresh_entry_rows()

        RetroButton(
            entry_header,
            text="+",
            bg_color=NEON_GREEN,
            command=add_entry_row,
            width=3,
            padx=4,
        ).pack(side="right")

        add_entry_row("bot", "index.js")

        buttons = tk.Frame(dialog, bg=BG_DARK)
        buttons.grid(row=4, column=0, columnspan=3, sticky="e", padx=15, pady=15)

        def save_bot():
            name = name_var.get().strip()
            path = path_var.get().strip()
            if not name:
                messagebox.showerror("Missing Name", "Give the Discord bot a name.", parent=dialog)
                return
            if not path or not os.path.isdir(path):
                messagebox.showerror("Missing Path", "Choose an existing Discord bot folder.", parent=dialog)
                return

            service_name = self.slugify_site_name(name)
            if any(bot["service_name"] == service_name for bot in self.discord_bot_paths):
                messagebox.showerror("Duplicate Discord Bot", f"A Discord bot named {service_name} already exists.", parent=dialog)
                return

            entries = []
            used_services = set()
            for row_data in entry_rows:
                label = row_data["name"].get().strip()
                node_file = row_data["file"].get().strip().replace("\\", "/")
                if not label or not node_file:
                    messagebox.showerror("Missing Entry", "Each bot entry needs a name and file.", parent=dialog)
                    return
                full_node_file = os.path.join(path, node_file)
                if not os.path.isfile(full_node_file):
                    messagebox.showerror("Missing Node File", f"Node file not found: {node_file}", parent=dialog)
                    return

                bot_service = f"{service_name}-{self.slugify_site_name(label)}"
                if bot_service in used_services:
                    messagebox.showerror("Duplicate Entry", f"Duplicate bot entry name: {label}", parent=dialog)
                    return
                used_services.add(bot_service)

                entries.append({
                    "name": label,
                    "file": node_file,
                    "service_name": bot_service,
                })

            self.discord_bot_paths.append({
                "name": name,
                "path": path,
                "service_name": service_name,
                "entries": entries,
            })
            self.save_discord_bot_paths()
            self.refresh_discord_bot_paths_list()
            self.refresh_discord_bot_control_panel()
            self.log(f"Discord bot path added: {name}")
            dialog.destroy()

        RetroButton(buttons, text="Cancel", bg_color=NEON_PURPLE, command=dialog.destroy, padx=10).pack(side="right", padx=5)
        RetroButton(buttons, text="Add Bot", bg_color=NEON_GREEN, command=save_bot, padx=10).pack(side="right", padx=5)

        dialog.columnconfigure(1, weight=1)

    def remove_discord_bot_path(self, bot):
        confirmed = messagebox.askyesno(
            "Remove Discord Bot",
            f"Remove {bot['name']} from the Discord bot path list?\n\nThis does not delete files from your Pi.",
        )
        if not confirmed:
            return

        self.discord_bot_paths = [item for item in self.discord_bot_paths if item["service_name"] != bot["service_name"]]
        self.save_discord_bot_paths()
        self.refresh_discord_bot_paths_list()
        self.refresh_discord_bot_control_panel()
        self.log(f"Discord bot path removed: {bot['name']}")

    def view_discord_bot_path(self, bot):
        path = bot["path"]
        if path and os.path.exists(path):
            os.startfile(path)
        else:
            self.log(f"Discord bot folder not found: {path}")

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
        services_body, canvas, _scrollbar = self.create_scroll_area(
            f,
            body_attr="services_body",
            padx=(0, 0),
            pady=(0, 15),
            scrollbar_padx=(0, 0),
        )
        self.scroll_canvases["Services"] = canvas

        service_body = self.add_collapsible_section(services_body, "SERVICE CONTROLS", font_size=16, start_open=True)

        buttons = [
            ("► START DOCKER STACK", "cd /srv/docker/compose/core && docker compose up -d"),
            ("■ STOP DOCKER STACK", "cd /srv/docker/compose/core && docker compose down"),
            ("↻ RESTART DOCKER STACK", "cd /srv/docker/compose/core && docker compose restart"),
            ("↻ RESTART GLANCE", "cd /srv/docker/compose/core && docker compose restart glance"),
            ("↻ REPLACE DOCKER COMPOSE", lambda: self.threaded(self.replace_docker_compose)),
            ("↻ RESTART HARDWARE MONITOR", "sudo systemctl restart pi-panel.service"),
            ("▣ VIEW HARDWARE MONITOR STATUS", "systemctl status pi-panel.service --no-pager"),
            ("▢ VIEW DOCKER CONTAINERS", "docker ps"),
        ]

        colors = [NEON_GREEN, NEON_ORANGE, NEON_YELLOW, NEON_ORANGE, NEON_YELLOW, NEON_CYAN, NEON_CYAN, NEON_CYAN]

        service_grid = tk.Frame(service_body, bg=BG_DARK)
        service_grid.pack(anchor="w", padx=20, pady=5)
        service_grid.columnconfigure(0, weight=1)
        service_grid.columnconfigure(1, weight=1)

        for index, ((text, cmd), color) in enumerate(zip(buttons, colors)):
            command = cmd if callable(cmd) else lambda c=cmd: self.threaded(lambda: self.run_single_command(c))
            btn = RetroButton(service_grid, text=text, bg_color=color, command=command)
            btn.config(width=34)
            btn.grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 15), pady=6)

        deploy_body = self.add_collapsible_section(services_body, "DEPLOY SELECTED FILES", font_size=14, start_open=True)

        deploy_buttons = [
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

        kuma_body = self.add_collapsible_section(services_body, "KUMA DATA BACKUP", font_size=14, start_open=True)

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

    def build_website_control_tab(self):
        f = self.frames["Website Control Panel"]

        RetroLabel(f, text="WEBSITE CONTROL PANEL", font_size=16, color=NEON_PINK).pack(anchor="w", padx=15, pady=(15, 10))
        tk.Frame(f, bg=NEON_PINK, height=1).pack(fill="x", padx=15, pady=(0, 15))

        actions = tk.Frame(f, bg=BG_DARK)
        actions.pack(fill="x", padx=20, pady=(0, 10))

        RetroButton(
            actions,
            text="REFRESH ALL STATUS",
            bg_color=NEON_CYAN,
            command=lambda: self.threaded(self.refresh_all_website_statuses),
        ).pack(side="left", padx=(0, 8))

        RetroButton(
            actions,
            text="SHOW COMPOSE SNIPPETS",
            bg_color=NEON_YELLOW,
            command=self.show_website_compose_snippets,
        ).pack(side="left")

        _body, canvas, _scrollbar = self.create_scroll_area(
            f,
            body_attr="website_control_body",
            padx=(20, 0),
            pady=(0, 15),
            scrollbar_padx=(0, 20),
        )
        self.scroll_canvases["Website Control Panel"] = canvas

        self.refresh_website_control_panel()

    def refresh_website_paths_list(self):
        if not hasattr(self, "website_paths_list"):
            return

        for child in self.website_paths_list.winfo_children():
            child.destroy()

        if not self.website_paths:
            RetroLabel(
                self.website_paths_list,
                text="No websites added yet. Click + to add one.",
                font_size=10,
                color=TEXT_GRAY,
            ).pack(anchor="w", pady=5)
            return

        for site in self.website_paths:
            row = tk.Frame(self.website_paths_list, bg=BG_DARK)
            row.pack(fill="x", pady=5)

            RetroLabel(row, text=f"{site['name']}  [{site['service_name']}]", font_size=11, color=NEON_CYAN).pack(side="left", padx=(0, 10))

            path_label = tk.Label(
                row,
                text=site["path"],
                bg=BG_DARK,
                fg=TEXT_GRAY,
                font=("Courier New", 9),
                anchor="w",
            )
            path_label.pack(side="left", fill="x", expand=True)

            RetroButton(row, text="View", bg_color=NEON_PURPLE, command=lambda s=site: self.view_website_path(s), padx=8).pack(side="right", padx=2)
            RetroButton(row, text="Remove", bg_color=NEON_ORANGE, command=lambda s=site: self.remove_website_path(s), padx=8).pack(side="right", padx=2)

    def refresh_discord_bot_paths_list(self):
        if not hasattr(self, "discord_bot_paths_list"):
            return

        for child in self.discord_bot_paths_list.winfo_children():
            child.destroy()

        if not self.discord_bot_paths:
            RetroLabel(
                self.discord_bot_paths_list,
                text="No Discord bots added yet. Click + to add one.",
                font_size=10,
                color=TEXT_GRAY,
            ).pack(anchor="w", pady=5)
            return

        for bot in self.discord_bot_paths:
            row = tk.Frame(self.discord_bot_paths_list, bg=BG_DARK)
            row.pack(fill="x", pady=5)

            RetroLabel(row, text=f"{bot['name']}  [{bot['service_name']}]", font_size=11, color=NEON_CYAN).pack(side="left", padx=(0, 10))

            path_label = tk.Label(
                row,
                text=bot["path"],
                bg=BG_DARK,
                fg=TEXT_GRAY,
                font=("Courier New", 9),
                anchor="w",
            )
            path_label.pack(side="left", fill="x", expand=True)

            RetroButton(row, text="View", bg_color=NEON_PURPLE, command=lambda b=bot: self.view_discord_bot_path(b), padx=8).pack(side="right", padx=2)
            RetroButton(row, text="Remove", bg_color=NEON_ORANGE, command=lambda b=bot: self.remove_discord_bot_path(b), padx=8).pack(side="right", padx=2)

    def refresh_website_control_panel(self):
        if not hasattr(self, "website_control_body"):
            return

        for child in self.website_control_body.winfo_children():
            child.destroy()

        self.website_status_labels = {}

        if not self.website_paths:
            RetroLabel(
                self.website_control_body,
                text="No websites configured. Add website paths from the Paths tab first.",
                font_size=11,
                color=TEXT_GRAY,
            ).pack(anchor="w", padx=10, pady=10)
            return

        for site in self.website_paths:
            self.add_website_control_section(site)

    def add_website_control_section(self, site):
        remote_path = self.remote_website_path(site)

        section = tk.Frame(self.website_control_body, bg=BG_DARK)
        section.pack(fill="x", pady=(0, 15))

        header = tk.Frame(section, bg=BG_DARK)
        header.pack(fill="x")

        RetroLabel(header, text=site["name"], font_size=14, color=NEON_PINK).pack(side="left")

        site_actions = tk.Frame(section, bg=BG_DARK)
        site_actions.pack(anchor="w", padx=10, pady=(6, 0))

        site_buttons = [
            ("LIMITED UPDATE", lambda s=site: self.open_limited_update_dialog(s), NEON_YELLOW),
            ("UPDATE FILES", lambda s=site: self.threaded(lambda: self.update_website_files(s)), NEON_CYAN),
            ("REMOVE ALL", lambda s=site: self.remove_website_from_compose(s), NEON_ORANGE),
            ("ADD ALL", lambda s=site: self.add_website_to_compose(s), NEON_GREEN),
        ]

        for index, (text, command, color) in enumerate(site_buttons):
            btn = RetroButton(site_actions, text=text, bg_color=color, command=command, padx=4, pady=3)
            btn.grid(row=0, column=index, sticky="w", padx=(0, 6), pady=3)

        tk.Frame(section, bg=NEON_PINK, height=1).pack(fill="x", pady=(5, 8))

        details = tk.Label(
            section,
            text=f"Local: {site['path']}\nRemote: {remote_path}",
            bg=BG_DARK,
            fg=TEXT_GRAY,
            font=("Courier New", 9),
            justify="left",
            anchor="w",
        )
        details.pack(fill="x", padx=10, pady=(0, 8))

        for deployable in site["deployables"]:
            self.add_deployable_control_row(section, site, deployable)

    def add_deployable_control_row(self, parent, site, deployable):
        row = tk.Frame(parent, bg=BG_DARK)
        row.pack(fill="x", padx=10, pady=5)

        title = f"{deployable['name']}  [{deployable['service_name']}]  {deployable['file']}  {deployable['host_port']}->{deployable['container_port']}"
        RetroLabel(row, text=title, font_size=10, color=NEON_CYAN).pack(side="left", padx=(0, 10))

        status = RetroLabel(row, text="X UNKNOWN", font_size=10, color=NEON_ORANGE)
        status.pack(side="right", padx=5)
        self.website_status_labels[deployable["service_name"]] = status

        controls = tk.Frame(parent, bg=BG_DARK)
        controls.pack(anchor="w", padx=10, pady=(0, 8))

        buttons = [
            ("CHECK", lambda d=deployable: self.threaded(lambda: self.check_website_status(d)), NEON_CYAN),
            ("START", lambda d=deployable: self.threaded(lambda: self.start_website(d)), NEON_GREEN),
            ("STOP", lambda d=deployable: self.threaded(lambda: self.stop_website(d)), NEON_ORANGE),
            ("RESTART", lambda d=deployable: self.threaded(lambda: self.restart_website(d)), NEON_YELLOW),
            ("LOGS", lambda d=deployable: self.threaded(lambda: self.show_website_logs(d)), NEON_PURPLE),
            ("ADD COMPOSE", lambda s=site, d=deployable: self.add_deployable_to_compose(s, d), NEON_GREEN),
            ("REMOVE COMPOSE", lambda d=deployable: self.remove_deployable_from_compose(d), NEON_ORANGE),
        ]

        for index, (text, command, color) in enumerate(buttons):
            btn = RetroButton(controls, text=text, bg_color=color, command=command, padx=3, pady=3)
            btn.grid(row=0, column=index, sticky="w", padx=(0, 4), pady=3)

    def build_discord_bot_control_tab(self):
        f = self.frames["Discord Bot Control"]

        RetroLabel(f, text="DISCORD BOT CONTROL", font_size=16, color=NEON_PINK).pack(anchor="w", padx=15, pady=(15, 10))
        tk.Frame(f, bg=NEON_PINK, height=1).pack(fill="x", padx=15, pady=(0, 15))

        actions = tk.Frame(f, bg=BG_DARK)
        actions.pack(fill="x", padx=20, pady=(0, 10))

        RetroButton(
            actions,
            text="REFRESH ALL STATUS",
            bg_color=NEON_CYAN,
            command=lambda: self.threaded(self.refresh_all_discord_bot_statuses),
        ).pack(side="left", padx=(0, 8))

        RetroButton(
            actions,
            text="SHOW COMPOSE SNIPPETS",
            bg_color=NEON_YELLOW,
            command=self.show_discord_bot_compose_snippets,
        ).pack(side="left")

        _body, canvas, _scrollbar = self.create_scroll_area(
            f,
            body_attr="discord_bot_control_body",
            padx=(20, 0),
            pady=(0, 15),
            scrollbar_padx=(0, 20),
        )
        self.scroll_canvases["Discord Bot Control"] = canvas

        self.refresh_discord_bot_control_panel()

    def refresh_discord_bot_control_panel(self):
        if not hasattr(self, "discord_bot_control_body"):
            return

        for child in self.discord_bot_control_body.winfo_children():
            child.destroy()

        self.discord_bot_status_labels = {}

        if not self.discord_bot_paths:
            RetroLabel(
                self.discord_bot_control_body,
                text="No Discord bots configured. Add Discord bot paths from the Paths tab first.",
                font_size=11,
                color=TEXT_GRAY,
            ).pack(anchor="w", padx=10, pady=10)
            return

        for bot in self.discord_bot_paths:
            self.add_discord_bot_control_section(bot)

    def add_discord_bot_control_section(self, bot):
        remote_path = self.remote_discord_bot_path(bot)

        section = tk.Frame(self.discord_bot_control_body, bg=BG_DARK)
        section.pack(fill="x", pady=(0, 15))

        header = tk.Frame(section, bg=BG_DARK)
        header.pack(fill="x")

        RetroLabel(header, text=bot["name"], font_size=14, color=NEON_PINK).pack(side="left")

        bot_actions = tk.Frame(section, bg=BG_DARK)
        bot_actions.pack(anchor="w", padx=10, pady=(6, 0))

        bot_buttons = [
            ("LIMITED UPDATE", lambda b=bot: self.open_limited_discord_bot_update_dialog(b), NEON_YELLOW),
            ("UPDATE FILES", lambda b=bot: self.threaded(lambda: self.update_discord_bot_files(b)), NEON_CYAN),
            ("REMOVE ALL", lambda b=bot: self.remove_discord_bot_from_compose(b), NEON_ORANGE),
            ("DEPLOY ALL", lambda b=bot: self.threaded(lambda: self.deploy_discord_bot(b)), NEON_GREEN),
        ]

        for index, (text, command, color) in enumerate(bot_buttons):
            btn = RetroButton(bot_actions, text=text, bg_color=color, command=command, padx=4, pady=3)
            btn.grid(row=0, column=index, sticky="w", padx=(0, 6), pady=3)

        tk.Frame(section, bg=NEON_PINK, height=1).pack(fill="x", pady=(5, 8))

        details = tk.Label(
            section,
            text=f"Local: {bot['path']}\nRemote: {remote_path}",
            bg=BG_DARK,
            fg=TEXT_GRAY,
            font=("Courier New", 9),
            justify="left",
            anchor="w",
        )
        details.pack(fill="x", padx=10, pady=(0, 8))

        for entry in bot["entries"]:
            self.add_discord_bot_entry_control_row(section, bot, entry)

    def add_discord_bot_entry_control_row(self, parent, bot, entry):
        row = tk.Frame(parent, bg=BG_DARK)
        row.pack(fill="x", padx=10, pady=5)

        title = f"{entry['name']}  [{entry['service_name']}]  {entry['file']}"
        RetroLabel(row, text=title, font_size=10, color=NEON_CYAN).pack(side="left", padx=(0, 10))

        status = RetroLabel(row, text="X UNKNOWN", font_size=10, color=NEON_ORANGE)
        status.pack(side="right", padx=5)
        self.discord_bot_status_labels[entry["service_name"]] = status

        controls = tk.Frame(parent, bg=BG_DARK)
        controls.pack(anchor="w", padx=10, pady=(0, 8))

        buttons = [
            ("CHECK", lambda e=entry: self.threaded(lambda: self.check_discord_bot_status(e)), NEON_CYAN),
            ("START", lambda e=entry: self.threaded(lambda: self.start_discord_bot(e)), NEON_GREEN),
            ("STOP", lambda e=entry: self.threaded(lambda: self.stop_discord_bot(e)), NEON_ORANGE),
            ("RESTART", lambda e=entry: self.threaded(lambda: self.restart_discord_bot(e)), NEON_YELLOW),
            ("LOGS", lambda e=entry: self.threaded(lambda: self.show_discord_bot_logs(e)), NEON_PURPLE),
            ("ADD COMPOSE", lambda b=bot, e=entry: self.add_discord_bot_entry_to_compose(b, e), NEON_GREEN),
            ("REMOVE COMPOSE", lambda e=entry: self.remove_discord_bot_entry_from_compose(e), NEON_ORANGE),
        ]

        for index, (text, command, color) in enumerate(buttons):
            btn = RetroButton(controls, text=text, bg_color=color, command=command, padx=3, pady=3)
            btn.grid(row=0, column=index, sticky="w", padx=(0, 4), pady=3)

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
            height=14,
            bg=BG_LIGHT,
            fg=NEON_GREEN,
            insertbackground=NEON_PINK,
            font=("Courier New", 9),
            relief="flat",
            bd=2,
        )
        self.log_box.pack(fill="x", expand=False, padx=20, pady=10)

        self.log_status = tk.StringVar(value="Ready")
        status_label = tk.Label(
            f,
            textvariable=self.log_status,
            bg=BG_DARK,
            fg=NEON_YELLOW,
            font=("Courier New", 9),
            anchor="w",
        )
        status_label.pack(fill="x", padx=20, pady=(0, 6))

        self.progress_value = 0
        self.progress_canvas = tk.Canvas(
            f,
            height=8,
            bg=BG_LIGHT,
            highlightthickness=1,
            highlightbackground=NEON_CYAN,
            relief="flat",
            bd=0,
        )
        self.progress_canvas.pack(fill="x", padx=20, pady=(0, 8))
        self.progress_fill = self.progress_canvas.create_rectangle(
            0, 0, 0, 8, fill=NEON_GREEN, outline=""
        )
        self.progress_canvas.bind("<Configure>", lambda _event: self.render_progress())

        log_buttons = tk.Frame(f, bg=BG_DARK)
        log_buttons.pack(anchor="w", padx=20, pady=(0, 10))

        RetroButton(log_buttons, text="EXPORT LOG", bg_color=NEON_CYAN, command=self.export_log, padx=10).pack(side="left", padx=(0, 8))
        RetroButton(log_buttons, text="CLEAR LOG", bg_color=NEON_PURPLE, command=self.clear_log, padx=10).pack(side="left")

    def clear_log(self):
        self.log_box.delete("1.0", tk.END)
        self.log_status.set("Log cleared.")
        self.set_progress(0)

    def export_log(self):
        selected = filedialog.asksaveasfilename(
            title="Export Log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="deploy_tool_log.txt",
        )
        if not selected:
            return

        with open(selected, "w", encoding="utf-8") as f:
            f.write(self.log_box.get("1.0", tk.END))

        self.log_status.set(f"Log exported: {selected}")

    def render_progress(self):
        if not hasattr(self, "progress_canvas"):
            return
        width = max(self.progress_canvas.winfo_width(), 1)
        value = max(0, min(100, getattr(self, "progress_value", 0)))
        self.progress_canvas.coords(self.progress_fill, 0, 0, int(width * value / 100), 8)

    def set_progress(self, value=None, pulse=False, label=None):
        if pulse:
            self.progress_value = min(95, getattr(self, "progress_value", 0) + 4)
        elif value is not None:
            self.progress_value = value

        if label and hasattr(self, "log_status"):
            self.log_status.set(label[:180])

        self.render_progress()
        self.root.update_idletasks()

    def clean_terminal_text(self, text):
        cleaned = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(text))
        cleaned = cleaned.replace("\x1b[?25l", "").replace("\x1b[?25h", "")
        cleaned = cleaned.replace("\r", "\n")
        return "\n".join(line.rstrip() for line in cleaned.splitlines() if line.strip())

    def write_log(self, text, show_in_box=True):
        cleaned = self.clean_terminal_text(text)
        if not cleaned:
            return

        if hasattr(self, "log_status"):
            last_line = cleaned.splitlines()[-1]
            self.log_status.set(last_line[:180])

        if not show_in_box:
            self.set_progress(pulse=True, label=cleaned.splitlines()[-1])
            return

        self.log_box.insert(tk.END, cleaned + "\n")
        self.log_box.see(tk.END)
        self.root.update_idletasks()

    def log(self, text):
        self.show_tab("Logs")
        self.write_log(text)

    def provision_log_write(self, text):
        """Write to the provision tab's output log"""
        cleaned = self.clean_terminal_text(text)
        if not cleaned:
            return
        self.provision_log.config(state="normal")
        self.provision_log.insert(tk.END, cleaned + "\n")
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

    def quiet_command(self, command):
        command = re.sub(
            r"\bdocker compose (up|down|restart)\b",
            r"docker compose --ansi never --progress plain \1",
            command,
        )
        return command

    def sudo_stdin_command(self, command):
        if command.strip().startswith("sudo ") and "sudo -S" not in command:
            return command.replace("sudo ", "sudo -S -p '' ", 1)
        return command

    def run(self, ssh, command, sudo_password=False):
        command = self.quiet_command(command)
        if sudo_password:
            command = self.sudo_stdin_command(command)
        self.log(f"$ {command}")
        self.provision_log_write(f"$ {command}")
        self.set_progress(5, label=f"Running: {command}")

        stdin, stdout, stderr = ssh.exec_command(command, get_pty=False)

        if sudo_password:
            stdin.write(self.password.get() + "\n")
            stdin.flush()

        last_progress = None
        for line in stdout:
            cleaned = self.clean_terminal_text(line.rstrip())
            if not cleaned:
                continue

            is_compose_progress = cleaned.lstrip().startswith(("[+] ", "Container ", "Network "))
            if is_compose_progress:
                if cleaned != last_progress:
                    self.write_log(cleaned, show_in_box=False)
                    last_progress = cleaned
                continue

            self.log(cleaned)
            self.provision_log_write(cleaned)

        err = stderr.read().decode(errors="ignore").strip()
        if err:
            cleaned_err = self.clean_terminal_text(err)
            if cleaned_err:
                kept_lines = []
                for line in cleaned_err.splitlines():
                    if line.lstrip().startswith(("[+] ", "Container ", "Network ")):
                        self.write_log(line, show_in_box=False)
                    else:
                        kept_lines.append(line)
                if kept_lines:
                    kept_err = "\n".join(kept_lines)
                    self.log(kept_err)
                    self.provision_log_write(kept_err)

        code = stdout.channel.recv_exit_status()
        if code != 0:
            self.set_progress(0, label="Command failed")
            raise RuntimeError(f"Command failed: {command}")
        self.set_progress(100, label="Command complete")

    def run_capture(self, ssh, command, sudo_password=False):
        command = self.quiet_command(command)
        if sudo_password:
            command = self.sudo_stdin_command(command)
        self.log(f"$ {command}")
        self.provision_log_write(f"$ {command}")
        self.set_progress(5, label=f"Running: {command}")

        stdin, stdout, stderr = ssh.exec_command(command, get_pty=False)

        if sudo_password:
            stdin.write(self.password.get() + "\n")
            stdin.flush()

        out = stdout.read().decode(errors="ignore").strip()
        err = stderr.read().decode(errors="ignore").strip()
        code = stdout.channel.recv_exit_status()

        if out:
            self.log(out)
            self.provision_log_write(out)
        if err:
            self.log(err)
            self.provision_log_write(err)

        self.set_progress(100 if code == 0 else 0, label="Command complete" if code == 0 else "Command failed")
        return code, out, err

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

    def upload_website_folder_contents(self, ssh, local_folder, remote_folder):
        self.log(f"Uploading website contents: {local_folder} -> {remote_folder}")
        self.provision_log_write(f"Uploading website: {os.path.basename(local_folder)}")

        skip_dirs = {".git", ".vs", "__pycache__", "node_modules", "uploads"}
        skip_files = {".DS_Store", "middleware.zip"}
        skip_rel_dirs = {os.path.normpath("public/img/user-profile")}

        self.prepare_remote_upload_folder(ssh, remote_folder)

        with SCPClient(ssh.get_transport()) as scp:
            for root, dirs, files in os.walk(local_folder):
                rel_root = os.path.relpath(root, local_folder)
                if rel_root == ".":
                    rel_root = ""

                dirs[:] = [
                    d for d in dirs
                    if d not in skip_dirs
                    and os.path.normpath(os.path.join(rel_root, d)) not in skip_rel_dirs
                ]

                remote_dir = remote_folder
                if rel_root:
                    remote_dir = remote_folder.rstrip("/") + "/" + rel_root.replace("\\", "/")
                    self.run(ssh, f"mkdir -p {shlex.quote(remote_dir)}")

                for file_name in files:
                    if file_name in skip_files or file_name.startswith("._"):
                        continue
                    local_file = os.path.join(root, file_name)
                    remote_file = remote_dir.rstrip("/") + "/" + file_name
                    scp.put(local_file, remote_file)

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

    def remote_website_path(self, site):
        return f"{REMOTE_WEBSITES_DIR}/{site['service_name']}"

    def remote_discord_bot_path(self, bot):
        return f"{REMOTE_DISCORD_BOTS_DIR}/{bot['service_name']}"

    def compose_service_command(self, service, command):
        quoted_dir = shlex.quote(REMOTE_DOCKER_DIR)
        quoted_service = shlex.quote(service)
        return f"cd {quoted_dir} && docker compose {command} {quoted_service}"

    def set_website_status(self, site, live):
        label = self.website_status_labels.get(site["service_name"])
        if not label:
            return

        if live:
            label.config(text="OK LIVE", fg=NEON_GREEN)
        else:
            label.config(text="X OFFLINE", fg=NEON_RED)

    def refresh_all_website_statuses(self):
        for site in self.website_paths:
            for deployable in site["deployables"]:
                self.check_website_status(deployable)

    def check_website_status(self, deployable):
        ssh = None
        try:
            ssh = self.connect()
            command = f"cd {shlex.quote(REMOTE_DOCKER_DIR)} && docker compose ps --status running --services"
            stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
            out = stdout.read().decode(errors="ignore").strip()
            err = stderr.read().decode(errors="ignore").strip()
            code = stdout.channel.recv_exit_status()
            if code != 0:
                raise RuntimeError(err or "Unable to read Docker Compose service status.")

            running_services = {line.strip() for line in out.splitlines() if line.strip()}
            live = deployable["service_name"] in running_services
            self.set_website_status(deployable, live)
            self.write_log(f"Website status for {deployable['name']}: {'live' if live else 'offline'}")
        except Exception as e:
            self.set_website_status(deployable, False)
            self.write_log(f"ERROR checking website status for {deployable['name']}: {e}")
        finally:
            if ssh:
                ssh.close()

    def update_website_files(self, site):
        ssh = None
        try:
            local_path = site["path"]
            if not local_path or not os.path.isdir(local_path):
                raise FileNotFoundError(f"Missing or invalid website folder: {site['name']}")

            remote_path = self.remote_website_path(site)
            ssh = self.connect()
            self.run(ssh, f"mkdir -p {shlex.quote(remote_path)}")
            self.upload_website_folder_contents(ssh, local_path, remote_path)
            for deployable in site["deployables"]:
                self.run(ssh, self.compose_service_command(deployable["service_name"], "restart"))
            self.log(f"Website files updated for {site['name']}.")
            for deployable in site["deployables"]:
                self.check_website_status(deployable)
        except Exception as e:
            self.log(f"ERROR updating website files for {site['name']}: {e}")
        finally:
            if ssh:
                ssh.close()

    def open_limited_update_dialog(self, site):
        local_root = site["path"]
        if not local_root or not os.path.isdir(local_root):
            messagebox.showerror("Missing Website Path", f"Missing or invalid website folder: {site['name']}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Limited Update - {site['name']}")
        dialog.configure(bg=BG_DARK)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("760x460")

        selected_files = []
        selected_set = set()

        RetroLabel(dialog, text="LIMITED UPDATE", font_size=16, color=NEON_PINK).pack(anchor="w", padx=15, pady=(15, 6))

        info = tk.Label(
            dialog,
            text=f"Source: {local_root}\nRemote: {self.remote_website_path(site)}",
            bg=BG_DARK,
            fg=TEXT_GRAY,
            font=("Courier New", 9),
            justify="left",
            anchor="w",
        )
        info.pack(fill="x", padx=15, pady=(0, 10))

        list_frame = tk.Frame(dialog, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        listbox = tk.Listbox(
            list_frame,
            bg=BG_LIGHT,
            fg=NEON_CYAN,
            selectbackground=NEON_PINK,
            selectforeground=BG_DARK,
            font=("Courier New", 9),
            relief="flat",
            bd=2,
            highlightthickness=1,
            highlightbackground=NEON_PURPLE,
            highlightcolor=NEON_PINK,
        )
        listbox.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(
            list_frame,
            orient="vertical",
            command=listbox.yview,
            bg=BG_LIGHT,
            troughcolor=BG_DARK,
            activebackground=NEON_PINK,
            highlightthickness=1,
            highlightbackground=NEON_CYAN,
            relief="flat",
            bd=0,
            width=14,
        )
        scrollbar.pack(side="right", fill="y")
        listbox.configure(yscrollcommand=scrollbar.set)

        def refresh_selected_list():
            listbox.delete(0, tk.END)
            for rel_path in selected_files:
                listbox.insert(tk.END, rel_path)

        def add_files():
            chosen = filedialog.askopenfilenames(parent=dialog, initialdir=local_root)
            if not chosen:
                return

            root_abs = os.path.abspath(local_root)
            for file_path in chosen:
                add_selected_file(file_path, root_abs)

            refresh_selected_list()

        def add_folder():
            selected_folder = filedialog.askdirectory(parent=dialog, initialdir=local_root)
            if not selected_folder:
                return

            root_abs = os.path.abspath(local_root)
            folder_abs = os.path.abspath(selected_folder)
            try:
                outside_root = os.path.commonpath([root_abs, folder_abs]) != root_abs
            except ValueError:
                outside_root = True
            if outside_root:
                messagebox.showerror("Outside Website Folder", f"Choose a folder inside the source path:\n{local_root}", parent=dialog)
                return

            for folder_root, dirs, files in os.walk(folder_abs):
                dirs[:] = [d for d in dirs if d not in {".git", ".vs", "__pycache__", "node_modules"}]
                for file_name in files:
                    if file_name in {".DS_Store"} or file_name.startswith("._"):
                        continue
                    add_selected_file(os.path.join(folder_root, file_name), root_abs)

            refresh_selected_list()

        def add_selected_file(file_path, root_abs):
            file_abs = os.path.abspath(file_path)
            try:
                outside_root = os.path.commonpath([root_abs, file_abs]) != root_abs
            except ValueError:
                outside_root = True
            if outside_root:
                messagebox.showerror("Outside Website Folder", f"Skipped file outside source path:\n{file_path}", parent=dialog)
                return

            rel_path = os.path.relpath(file_abs, root_abs).replace("\\", "/")
            if rel_path not in selected_set:
                selected_files.append(rel_path)
                selected_set.add(rel_path)

        def remove_selected():
            selections = list(listbox.curselection())
            if not selections:
                return

            for index in reversed(selections):
                rel_path = selected_files.pop(index)
                selected_set.discard(rel_path)
            refresh_selected_list()

        def upload_selected():
            if not selected_files:
                messagebox.showerror("No Files Selected", "Choose at least one file to upload.", parent=dialog)
                return

            files_to_upload = list(selected_files)
            dialog.destroy()
            self.threaded(lambda: self.limited_update_website_files(site, files_to_upload))

        button_frame = tk.Frame(dialog, bg=BG_DARK)
        button_frame.pack(fill="x", padx=15, pady=(0, 15))

        RetroButton(button_frame, text="ADD FILES", bg_color=NEON_GREEN, command=add_files, padx=10).pack(side="left", padx=(0, 8))
        RetroButton(button_frame, text="ADD FOLDER", bg_color=NEON_YELLOW, command=add_folder, padx=10).pack(side="left", padx=(0, 8))
        RetroButton(button_frame, text="REMOVE SELECTED", bg_color=NEON_ORANGE, command=remove_selected, padx=10).pack(side="left", padx=(0, 8))
        RetroButton(button_frame, text="UPLOAD SELECTED", bg_color=NEON_CYAN, command=upload_selected, padx=10).pack(side="right", padx=(8, 0))
        RetroButton(button_frame, text="CANCEL", bg_color=NEON_PURPLE, command=dialog.destroy, padx=10).pack(side="right")

    def limited_update_website_files(self, site, rel_paths):
        ssh = None
        try:
            local_root = site["path"]
            remote_root = self.remote_website_path(site)
            if not local_root or not os.path.isdir(local_root):
                raise FileNotFoundError(f"Missing or invalid website folder: {site['name']}")

            root_abs = os.path.abspath(local_root)
            ssh = self.connect()

            for rel_path in rel_paths:
                local_file = os.path.abspath(os.path.join(local_root, rel_path))
                try:
                    outside_root = os.path.commonpath([root_abs, local_file]) != root_abs
                except ValueError:
                    outside_root = True
                if outside_root:
                    raise ValueError(f"Refusing to upload outside website folder: {rel_path}")
                if not os.path.isfile(local_file):
                    raise FileNotFoundError(f"Missing selected file: {rel_path}")

                remote_file = remote_root.rstrip("/") + "/" + rel_path.replace("\\", "/")
                self.upload_file(ssh, local_file, remote_file)

            for deployable in site["deployables"]:
                self.run(ssh, self.compose_service_command(deployable["service_name"], "restart"))

            ssh.close()
            ssh = None
            self.log(f"Limited update uploaded {len(rel_paths)} file(s) for {site['name']}.")
            for deployable in site["deployables"]:
                self.check_website_status(deployable)
        except Exception as e:
            self.log(f"ERROR limited updating website files for {site['name']}: {e}")
        finally:
            if ssh:
                ssh.close()

    def start_website(self, site):
        self.run_website_compose_action(site, "up -d", "started")

    def stop_website(self, site):
        self.run_website_compose_action(site, "stop", "stopped")

    def restart_website(self, site):
        self.run_website_compose_action(site, "restart", "restarted")

    def show_website_logs(self, site):
        self.run_website_compose_action(site, "logs --tail 80", "logs shown", refresh_status=False)

    def website_compose_markers(self, deployable):
        service = deployable["service_name"]
        return (
            f"# BEGIN DEPLOY TOOL WEBSITE {service}",
            f"# END DEPLOY TOOL WEBSITE {service}",
        )

    def website_compose_block(self, site, deployable):
        service = deployable["service_name"]
        remote_path = self.remote_website_path(site)
        host_port = deployable["host_port"]
        container_port = deployable["container_port"]
        node_file = deployable["file"]
        start_marker, end_marker = self.website_compose_markers(deployable)
        return (
            f"\n  {start_marker}\n"
            f"  {service}:\n"
            "    image: node:20-bookworm-slim\n"
            f"    container_name: {service}\n"
            "    restart: unless-stopped\n"
            "    working_dir: /app\n"
            f"    command: sh -c \"npm ci --omit=dev && node {node_file}\"\n"
            "    ports:\n"
            f"      - \"{host_port}:{container_port}\"\n"
            "    volumes:\n"
            f"      - {remote_path}:/app\n"
            f"  {end_marker}\n"
        )

    def add_deployable_to_compose(self, site, deployable):
        try:
            compose_path = self.require_file_path("docker_compose", "Docker compose")

            with open(compose_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not re.search(r"(?m)^services:\s*$", content):
                raise ValueError("Docker compose file does not contain a top-level services: section.")

            start_marker, _end_marker = self.website_compose_markers(deployable)
            if start_marker in content:
                self.log(f"Deployable {deployable['name']} is already in Docker Compose.")
                return

            separator = "" if content.endswith("\n") else "\n"
            block = self.website_compose_block(site, deployable)

            with open(compose_path, "w", encoding="utf-8") as f:
                f.write(content + separator + block)

            self.log(f"Deployable {deployable['name']} added to Docker Compose: {compose_path}")
        except Exception as e:
            self.log(f"ERROR adding deployable to Docker Compose for {deployable['name']}: {e}")

    def remove_deployable_from_compose(self, deployable):
        try:
            compose_path = self.require_file_path("docker_compose", "Docker compose")

            with open(compose_path, "r", encoding="utf-8") as f:
                content = f.read()

            start_marker, end_marker = self.website_compose_markers(deployable)
            pattern = re.compile(
                rf"\n?  {re.escape(start_marker)}\n.*?\n  {re.escape(end_marker)}\n?",
                re.DOTALL,
            )
            updated, count = pattern.subn("\n", content, count=1)

            if count == 0:
                self.log(f"Deployable {deployable['name']} was not found in Docker Compose.")
                return

            with open(compose_path, "w", encoding="utf-8") as f:
                f.write(updated.rstrip() + "\n")

            self.log(f"Deployable {deployable['name']} removed from Docker Compose: {compose_path}")
        except Exception as e:
            self.log(f"ERROR removing deployable from Docker Compose for {deployable['name']}: {e}")

    def add_website_to_compose(self, site):
        try:
            compose_path = self.require_file_path("docker_compose", "Docker compose")

            with open(compose_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not re.search(r"(?m)^services:\s*$", content):
                raise ValueError("Docker compose file does not contain a top-level services: section.")

            blocks = []
            for deployable in site["deployables"]:
                start_marker, _end_marker = self.website_compose_markers(deployable)
                if start_marker in content:
                    self.log(f"Deployable {deployable['name']} is already in Docker Compose.")
                    continue
                blocks.append(self.website_compose_block(site, deployable))

            if not blocks:
                return

            separator = "" if content.endswith("\n") else "\n"

            with open(compose_path, "w", encoding="utf-8") as f:
                f.write(content + separator + "".join(blocks))

            self.log(f"Website {site['name']} added to Docker Compose: {compose_path}")
        except Exception as e:
            self.log(f"ERROR adding website to Docker Compose for {site['name']}: {e}")

    def remove_website_from_compose(self, site):
        try:
            compose_path = self.require_file_path("docker_compose", "Docker compose")

            with open(compose_path, "r", encoding="utf-8") as f:
                content = f.read()

            updated = content
            total_removed = 0
            for deployable in site["deployables"]:
                start_marker, end_marker = self.website_compose_markers(deployable)
                pattern = re.compile(
                    rf"\n?  {re.escape(start_marker)}\n.*?\n  {re.escape(end_marker)}\n?",
                    re.DOTALL,
                )
                updated, count = pattern.subn("\n", updated, count=1)
                total_removed += count

            if total_removed == 0:
                self.log(f"Website {site['name']} was not found in Docker Compose.")
                return

            with open(compose_path, "w", encoding="utf-8") as f:
                f.write(updated.rstrip() + "\n")

            self.log(f"Website {site['name']} removed from Docker Compose: {compose_path}")
        except Exception as e:
            self.log(f"ERROR removing website from Docker Compose for {site['name']}: {e}")

    def run_website_compose_action(self, deployable, compose_action, done_text, refresh_status=True):
        ssh = None
        try:
            ssh = self.connect()
            self.run(ssh, self.compose_service_command(deployable["service_name"], compose_action))
            self.log(f"Deployable {deployable['name']} {done_text}.")
            if refresh_status:
                self.check_website_status(deployable)
        except Exception as e:
            self.log(f"ERROR running website action for {deployable['name']}: {e}")
            if refresh_status:
                self.set_website_status(deployable, False)
        finally:
            if ssh:
                ssh.close()

    def show_website_compose_snippets(self):
        if not self.website_paths:
            self.log("No website paths configured.")
            return

        self.log("Website Docker Compose snippets:")
        for site in self.website_paths:
            for deployable in site["deployables"]:
                self.log(self.website_compose_block(site, deployable))

    def set_discord_bot_status(self, entry, live):
        label = self.discord_bot_status_labels.get(entry["service_name"])
        if not label:
            return

        if live:
            label.config(text="OK RUNNING", fg=NEON_GREEN)
        else:
            label.config(text="X STOPPED", fg=NEON_RED)

    def refresh_all_discord_bot_statuses(self):
        for bot in self.discord_bot_paths:
            for entry in bot["entries"]:
                self.check_discord_bot_status(entry)

    def check_discord_bot_status(self, entry):
        ssh = None
        try:
            ssh = self.connect()
            command = f"cd {shlex.quote(REMOTE_DOCKER_DIR)} && docker compose ps --status running --services"
            stdin, stdout, stderr = ssh.exec_command(command, get_pty=True)
            out = stdout.read().decode(errors="ignore").strip()
            err = stderr.read().decode(errors="ignore").strip()
            code = stdout.channel.recv_exit_status()
            if code != 0:
                raise RuntimeError(err or "Unable to read Docker Compose service status.")

            running_services = {line.strip() for line in out.splitlines() if line.strip()}
            live = entry["service_name"] in running_services
            self.set_discord_bot_status(entry, live)
            self.write_log(f"Discord bot status for {entry['name']}: {'running' if live else 'stopped'}")
        except Exception as e:
            self.set_discord_bot_status(entry, False)
            self.write_log(f"ERROR checking Discord bot status for {entry['name']}: {e}")
        finally:
            if ssh:
                ssh.close()

    def discord_bot_is_running(self, ssh, entry):
        command = f"cd {shlex.quote(REMOTE_DOCKER_DIR)} && docker compose ps --status running --services"
        code, out, err = self.run_capture(ssh, command)
        if code != 0:
            raise RuntimeError(err or "Unable to read Docker Compose service status.")
        running_services = {line.strip() for line in out.splitlines() if line.strip()}
        return entry["service_name"] in running_services

    def log_discord_bot_diagnostics(self, ssh, entry):
        service = entry["service_name"]
        quoted_dir = shlex.quote(REMOTE_DOCKER_DIR)
        quoted_service = shlex.quote(service)
        self.log(f"Diagnostics for Discord bot entry {entry['name']} [{service}]:")

        checks = [
            ("Compose status", f"cd {quoted_dir} && docker compose ps {quoted_service}"),
            ("Recent logs", f"cd {quoted_dir} && docker compose logs --tail 120 {quoted_service}"),
            (
                "Container exit details",
                f"docker inspect {quoted_service} --format "
                "'State={{.State.Status}} ExitCode={{.State.ExitCode}} Error={{.State.Error}} FinishedAt={{.State.FinishedAt}}'",
            ),
        ]

        for label, command in checks:
            code, out, err = self.run_capture(ssh, command)
            if code == 0:
                details = out or "(no output)"
            else:
                details = err or out or f"{label} command failed."
            self.log(f"{label}:\n{details}")

    def update_discord_bot_files(self, bot):
        ssh = None
        try:
            local_path = bot["path"]
            if not local_path or not os.path.isdir(local_path):
                raise FileNotFoundError(f"Missing or invalid Discord bot folder: {bot['name']}")

            remote_path = self.remote_discord_bot_path(bot)
            ssh = self.connect()
            self.run(ssh, f"mkdir -p {shlex.quote(remote_path)}")
            self.upload_website_folder_contents(ssh, local_path, remote_path)
            for entry in bot["entries"]:
                self.run(ssh, self.compose_service_command(entry["service_name"], "restart"))

            self.log(f"Discord bot files updated for {bot['name']}.")
            for entry in bot["entries"]:
                self.check_discord_bot_status(entry)
        except Exception as e:
            self.log(f"ERROR updating Discord bot files for {bot['name']}: {e}")
        finally:
            if ssh:
                ssh.close()

    def deploy_discord_bot(self, bot):
        ssh = None
        try:
            local_path = bot["path"]
            if not local_path or not os.path.isdir(local_path):
                raise FileNotFoundError(f"Missing or invalid Discord bot folder: {bot['name']}")

            compose_path = self.require_file_path("docker_compose", "Docker compose")
            self.remove_discord_bot_from_compose(bot)
            self.add_discord_bot_to_compose(bot)

            remote_path = self.remote_discord_bot_path(bot)
            ssh = self.connect()
            self.run(ssh, f"mkdir -p {shlex.quote(remote_path)}")
            self.upload_website_folder_contents(ssh, local_path, remote_path)
            self.upload_file(ssh, compose_path, f"{REMOTE_DOCKER_DIR}/docker-compose.yml")

            for entry in bot["entries"]:
                self.run(ssh, self.compose_service_command(entry["service_name"], "up -d"))
                live = self.discord_bot_is_running(ssh, entry)
                self.set_discord_bot_status(entry, live)
                if live:
                    self.write_log(f"Discord bot status for {entry['name']}: running")
                else:
                    self.write_log(f"Discord bot status for {entry['name']}: stopped")
                    self.log_discord_bot_diagnostics(ssh, entry)

            self.log(f"Discord bot deployed: {bot['name']}")
        except Exception as e:
            self.log(f"ERROR deploying Discord bot {bot['name']}: {e}")
            if ssh:
                for entry in bot.get("entries", []):
                    try:
                        self.log_discord_bot_diagnostics(ssh, entry)
                    except Exception as diag_error:
                        self.log(f"ERROR collecting Discord bot diagnostics for {entry['name']}: {diag_error}")
        finally:
            if ssh:
                ssh.close()

    def open_limited_discord_bot_update_dialog(self, bot):
        local_root = bot["path"]
        if not local_root or not os.path.isdir(local_root):
            messagebox.showerror("Missing Discord Bot Path", f"Missing or invalid Discord bot folder: {bot['name']}")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Limited Update - {bot['name']}")
        dialog.configure(bg=BG_DARK)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("760x460")

        selected_files = []
        selected_set = set()

        RetroLabel(dialog, text="LIMITED UPDATE", font_size=16, color=NEON_PINK).pack(anchor="w", padx=15, pady=(15, 6))

        info = tk.Label(
            dialog,
            text=f"Source: {local_root}\nRemote: {self.remote_discord_bot_path(bot)}",
            bg=BG_DARK,
            fg=TEXT_GRAY,
            font=("Courier New", 9),
            justify="left",
            anchor="w",
        )
        info.pack(fill="x", padx=15, pady=(0, 10))

        list_frame = tk.Frame(dialog, bg=BG_DARK)
        list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        listbox = tk.Listbox(
            list_frame,
            bg=BG_LIGHT,
            fg=NEON_CYAN,
            selectbackground=NEON_PINK,
            selectforeground=BG_DARK,
            font=("Courier New", 9),
            relief="flat",
            bd=2,
            highlightthickness=1,
            highlightbackground=NEON_PURPLE,
            highlightcolor=NEON_PINK,
        )
        listbox.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(
            list_frame,
            orient="vertical",
            command=listbox.yview,
            bg=BG_LIGHT,
            troughcolor=BG_DARK,
            activebackground=NEON_PINK,
            highlightthickness=1,
            highlightbackground=NEON_CYAN,
            relief="flat",
            bd=0,
            width=14,
        )
        scrollbar.pack(side="right", fill="y")
        listbox.configure(yscrollcommand=scrollbar.set)

        def refresh_selected_list():
            listbox.delete(0, tk.END)
            for rel_path in selected_files:
                listbox.insert(tk.END, rel_path)

        def add_selected_file(file_path, root_abs):
            file_abs = os.path.abspath(file_path)
            try:
                outside_root = os.path.commonpath([root_abs, file_abs]) != root_abs
            except ValueError:
                outside_root = True
            if outside_root:
                messagebox.showerror("Outside Bot Folder", f"Skipped file outside source path:\n{file_path}", parent=dialog)
                return

            rel_path = os.path.relpath(file_abs, root_abs).replace("\\", "/")
            if rel_path not in selected_set:
                selected_files.append(rel_path)
                selected_set.add(rel_path)

        def add_files():
            chosen = filedialog.askopenfilenames(parent=dialog, initialdir=local_root)
            if not chosen:
                return
            root_abs = os.path.abspath(local_root)
            for file_path in chosen:
                add_selected_file(file_path, root_abs)
            refresh_selected_list()

        def add_folder():
            selected_folder = filedialog.askdirectory(parent=dialog, initialdir=local_root)
            if not selected_folder:
                return

            root_abs = os.path.abspath(local_root)
            folder_abs = os.path.abspath(selected_folder)
            try:
                outside_root = os.path.commonpath([root_abs, folder_abs]) != root_abs
            except ValueError:
                outside_root = True
            if outside_root:
                messagebox.showerror("Outside Bot Folder", f"Choose a folder inside the source path:\n{local_root}", parent=dialog)
                return

            for folder_root, dirs, files in os.walk(folder_abs):
                dirs[:] = [d for d in dirs if d not in {".git", ".vs", "__pycache__", "node_modules"}]
                for file_name in files:
                    if file_name in {".DS_Store"} or file_name.startswith("._"):
                        continue
                    add_selected_file(os.path.join(folder_root, file_name), root_abs)
            refresh_selected_list()

        def remove_selected():
            selections = list(listbox.curselection())
            if not selections:
                return
            for index in reversed(selections):
                rel_path = selected_files.pop(index)
                selected_set.discard(rel_path)
            refresh_selected_list()

        def upload_selected():
            if not selected_files:
                messagebox.showerror("No Files Selected", "Choose at least one file to upload.", parent=dialog)
                return
            files_to_upload = list(selected_files)
            dialog.destroy()
            self.threaded(lambda: self.limited_update_discord_bot_files(bot, files_to_upload))

        button_frame = tk.Frame(dialog, bg=BG_DARK)
        button_frame.pack(fill="x", padx=15, pady=(0, 15))

        RetroButton(button_frame, text="ADD FILES", bg_color=NEON_GREEN, command=add_files, padx=10).pack(side="left", padx=(0, 8))
        RetroButton(button_frame, text="ADD FOLDER", bg_color=NEON_YELLOW, command=add_folder, padx=10).pack(side="left", padx=(0, 8))
        RetroButton(button_frame, text="REMOVE SELECTED", bg_color=NEON_ORANGE, command=remove_selected, padx=10).pack(side="left", padx=(0, 8))
        RetroButton(button_frame, text="UPLOAD SELECTED", bg_color=NEON_CYAN, command=upload_selected, padx=10).pack(side="right", padx=(8, 0))
        RetroButton(button_frame, text="CANCEL", bg_color=NEON_PURPLE, command=dialog.destroy, padx=10).pack(side="right")

    def limited_update_discord_bot_files(self, bot, rel_paths):
        ssh = None
        try:
            local_root = bot["path"]
            remote_root = self.remote_discord_bot_path(bot)
            if not local_root or not os.path.isdir(local_root):
                raise FileNotFoundError(f"Missing or invalid Discord bot folder: {bot['name']}")

            root_abs = os.path.abspath(local_root)
            ssh = self.connect()

            for rel_path in rel_paths:
                local_file = os.path.abspath(os.path.join(local_root, rel_path))
                try:
                    outside_root = os.path.commonpath([root_abs, local_file]) != root_abs
                except ValueError:
                    outside_root = True
                if outside_root:
                    raise ValueError(f"Refusing to upload outside Discord bot folder: {rel_path}")
                if not os.path.isfile(local_file):
                    raise FileNotFoundError(f"Missing selected file: {rel_path}")

                remote_file = remote_root.rstrip("/") + "/" + rel_path.replace("\\", "/")
                self.upload_file(ssh, local_file, remote_file)

            for entry in bot["entries"]:
                self.run(ssh, self.compose_service_command(entry["service_name"], "restart"))

            ssh.close()
            ssh = None
            self.log(f"Limited update uploaded {len(rel_paths)} file(s) for {bot['name']}.")
            for entry in bot["entries"]:
                self.check_discord_bot_status(entry)
        except Exception as e:
            self.log(f"ERROR limited updating Discord bot files for {bot['name']}: {e}")
        finally:
            if ssh:
                ssh.close()

    def start_discord_bot(self, entry):
        self.run_discord_bot_compose_action(entry, "up -d", "started")

    def stop_discord_bot(self, entry):
        self.run_discord_bot_compose_action(entry, "stop", "stopped")

    def restart_discord_bot(self, entry):
        self.run_discord_bot_compose_action(entry, "restart", "restarted")

    def show_discord_bot_logs(self, entry):
        self.run_discord_bot_compose_action(entry, "logs --tail 80", "logs shown", refresh_status=False)

    def discord_bot_compose_markers(self, entry):
        service = entry["service_name"]
        return (
            f"# BEGIN DEPLOY TOOL DISCORD BOT {service}",
            f"# END DEPLOY TOOL DISCORD BOT {service}",
        )

    def discord_bot_compose_block(self, bot, entry):
        service = entry["service_name"]
        remote_path = self.remote_discord_bot_path(bot)
        node_file = entry["file"]
        start_marker, end_marker = self.discord_bot_compose_markers(entry)
        return (
            f"\n  {start_marker}\n"
            f"  {service}:\n"
            "    image: node:20-bookworm-slim\n"
            f"    container_name: {service}\n"
            "    restart: unless-stopped\n"
            "    working_dir: /app\n"
            f"    command: sh -c \"if [ -f package-lock.json ]; then npm ci --omit=dev; elif [ -f package.json ]; then npm install --omit=dev; fi && node {node_file}\"\n"
            "    volumes:\n"
            f"      - {remote_path}:/app\n"
            f"  {end_marker}\n"
        )

    def add_discord_bot_entry_to_compose(self, bot, entry):
        try:
            compose_path = self.require_file_path("docker_compose", "Docker compose")

            with open(compose_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not re.search(r"(?m)^services:\s*$", content):
                raise ValueError("Docker compose file does not contain a top-level services: section.")

            start_marker, _end_marker = self.discord_bot_compose_markers(entry)
            if start_marker in content:
                self.log(f"Discord bot entry {entry['name']} is already in Docker Compose.")
                return

            separator = "" if content.endswith("\n") else "\n"
            block = self.discord_bot_compose_block(bot, entry)

            with open(compose_path, "w", encoding="utf-8") as f:
                f.write(content + separator + block)

            self.log(f"Discord bot entry {entry['name']} added to Docker Compose: {compose_path}")
        except Exception as e:
            self.log(f"ERROR adding Discord bot entry to Docker Compose for {entry['name']}: {e}")

    def remove_discord_bot_entry_from_compose(self, entry):
        try:
            compose_path = self.require_file_path("docker_compose", "Docker compose")

            with open(compose_path, "r", encoding="utf-8") as f:
                content = f.read()

            start_marker, end_marker = self.discord_bot_compose_markers(entry)
            pattern = re.compile(
                rf"\n?  {re.escape(start_marker)}\n.*?\n  {re.escape(end_marker)}\n?",
                re.DOTALL,
            )
            updated, count = pattern.subn("\n", content, count=1)

            if count == 0:
                self.log(f"Discord bot entry {entry['name']} was not found in Docker Compose.")
                return

            with open(compose_path, "w", encoding="utf-8") as f:
                f.write(updated.rstrip() + "\n")

            self.log(f"Discord bot entry {entry['name']} removed from Docker Compose: {compose_path}")
        except Exception as e:
            self.log(f"ERROR removing Discord bot entry from Docker Compose for {entry['name']}: {e}")

    def add_discord_bot_to_compose(self, bot):
        try:
            compose_path = self.require_file_path("docker_compose", "Docker compose")

            with open(compose_path, "r", encoding="utf-8") as f:
                content = f.read()

            if not re.search(r"(?m)^services:\s*$", content):
                raise ValueError("Docker compose file does not contain a top-level services: section.")

            blocks = []
            for entry in bot["entries"]:
                start_marker, _end_marker = self.discord_bot_compose_markers(entry)
                if start_marker in content:
                    self.log(f"Discord bot entry {entry['name']} is already in Docker Compose.")
                    continue
                blocks.append(self.discord_bot_compose_block(bot, entry))

            if not blocks:
                return

            separator = "" if content.endswith("\n") else "\n"

            with open(compose_path, "w", encoding="utf-8") as f:
                f.write(content + separator + "".join(blocks))

            self.log(f"Discord bot {bot['name']} added to Docker Compose: {compose_path}")
        except Exception as e:
            self.log(f"ERROR adding Discord bot to Docker Compose for {bot['name']}: {e}")

    def remove_discord_bot_from_compose(self, bot):
        try:
            compose_path = self.require_file_path("docker_compose", "Docker compose")

            with open(compose_path, "r", encoding="utf-8") as f:
                content = f.read()

            updated = content
            total_removed = 0
            for entry in bot["entries"]:
                start_marker, end_marker = self.discord_bot_compose_markers(entry)
                pattern = re.compile(
                    rf"\n?  {re.escape(start_marker)}\n.*?\n  {re.escape(end_marker)}\n?",
                    re.DOTALL,
                )
                updated, count = pattern.subn("\n", updated, count=1)
                total_removed += count

            if total_removed == 0:
                self.log(f"Discord bot {bot['name']} was not found in Docker Compose.")
                return

            with open(compose_path, "w", encoding="utf-8") as f:
                f.write(updated.rstrip() + "\n")

            self.log(f"Discord bot {bot['name']} removed from Docker Compose: {compose_path}")
        except Exception as e:
            self.log(f"ERROR removing Discord bot from Docker Compose for {bot['name']}: {e}")

    def run_discord_bot_compose_action(self, entry, compose_action, done_text, refresh_status=True):
        ssh = None
        try:
            ssh = self.connect()
            self.run(ssh, self.compose_service_command(entry["service_name"], compose_action))
            self.log(f"Discord bot entry {entry['name']} {done_text}.")
            if refresh_status:
                live = self.discord_bot_is_running(ssh, entry)
                self.set_discord_bot_status(entry, live)
                if live:
                    self.write_log(f"Discord bot status for {entry['name']}: running")
                else:
                    self.write_log(f"Discord bot status for {entry['name']}: stopped")
                    self.log_discord_bot_diagnostics(ssh, entry)
        except Exception as e:
            self.log(f"ERROR running Discord bot action for {entry['name']}: {e}")
            if refresh_status:
                self.set_discord_bot_status(entry, False)
                if ssh:
                    try:
                        self.log_discord_bot_diagnostics(ssh, entry)
                    except Exception as diag_error:
                        self.log(f"ERROR collecting Discord bot diagnostics for {entry['name']}: {diag_error}")
        finally:
            if ssh:
                ssh.close()

    def show_discord_bot_compose_snippets(self):
        if not self.discord_bot_paths:
            self.log("No Discord bot paths configured.")
            return

        self.log("Discord bot Docker Compose snippets:")
        for bot in self.discord_bot_paths:
            for entry in bot["entries"]:
                self.log(self.discord_bot_compose_block(bot, entry))

    def replace_docker_compose(self):
        ssh = None
        try:
            compose_path = self.require_file_path("docker_compose", "Docker compose")
            ssh = self.connect()
            self.run(ssh, f"mkdir -p {shlex.quote(REMOTE_DOCKER_DIR)}")
            self.run(ssh, f"cp {REMOTE_DOCKER_DIR}/docker-compose.yml {REMOTE_DOCKER_DIR}/docker-compose.yml.bak 2>/dev/null || true")
            self.upload_file(ssh, compose_path, f"{REMOTE_DOCKER_DIR}/docker-compose.yml")
            self.run(ssh, f"cd {REMOTE_DOCKER_DIR} && docker compose up -d")
            ssh.close()
            self.log("Docker compose replaced and stack started from the corrected file.")
        except Exception as e:
            self.log(f"ERROR: {e}")
            if ssh:
                ssh.close()

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
