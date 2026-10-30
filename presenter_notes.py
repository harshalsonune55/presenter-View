"""Presenter View - shows the poster on the audience screen and your speaking notes on your own screen.

The notes window is hidden from screen sharing/recording. With a projector or second display,
the poster goes full screen there and only your laptop shows the notes.
"""
import ctypes
import json
import os
import sys
import time
import tkinter as tk
from tkinter import filedialog

from PIL import Image, ImageTk

if getattr(sys, "frozen", False):  # packaged app: keep user data outside the app bundle
    if sys.platform == "darwin":
        HERE = os.path.expanduser("~/Library/Application Support/Presenter View")
    else:
        HERE = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Presenter View")
    os.makedirs(HERE, exist_ok=True)
else:
    HERE = os.path.dirname(os.path.abspath(__file__))
NOTES_FILE = os.path.join(HERE, "notes.txt")
SETTINGS_FILE = os.path.join(HERE, "settings.json")
TITLE = "Presenter View"
SAMPLE = """# Introduction
Good morning everyone.
Introduce yourself and the title of the poster.
State the problem in one sentence.

# Method
How the data was collected.
Point to the diagram on the left of the poster.

# Results
Lead with the biggest number.
Point to the main chart.

# Conclusion
Three take-aways.
Thank the audience and invite questions.
"""

BG, PANEL, LINE = "#0f1115", "#171a21", "#262a33"
FG, MUTED, ACCENT, GOOD, BAD = "#eef0f3", "#8b919c", "#4f8cff", "#3ecf8e", "#ff6b6b"
BLUE, YELLOW, RED, GREEN = "#2563eb", "#e0a800", "#dc3545", "#16a34a"
UI = "Helvetica" if sys.platform == "darwin" else "Segoe UI"
MONO = "Menlo" if sys.platform == "darwin" else "Consolas"
FILETYPES = [("Poster (PDF or image)", "*.pdf *.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff"),
             ("PDF", "*.pdf"), ("Images", "*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tif *.tiff")]


def hide_from_capture(window):
    """Keep the window off screen shares and recordings. Returns True on success."""
    window.update_idletasks()
    if sys.platform == "darwin":
        from AppKit import NSApp
        ok = False
        for w in NSApp.windows():
            if w.title() == TITLE:
                w.setSharingType_(0)  # NSWindowSharingNone
                ok = True
        return ok
    user32 = ctypes.windll.user32
    hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
    return bool(user32.SetWindowDisplayAffinity(hwnd, 0x11) or user32.SetWindowDisplayAffinity(hwnd, 0x01))


def screens(root):
    """Displays as (x, y, width, height) in Tk coordinates; the first one is the main display."""
    if sys.platform == "darwin":
        from AppKit import NSScreen
        all_screens = NSScreen.screens()
        main_h = all_screens[0].frame().size.height
        out = []
        for s in all_screens:
            f = s.frame()
            out.append((int(f.origin.x), int(main_h - f.origin.y - f.size.height), int(f.size.width), int(f.size.height)))
        return out
    if sys.platform == "win32":
        from ctypes import wintypes

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        out = []

        def found(monitor, dc, rect, data):
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(info)
            ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info))
            r = info.rcMonitor
            item = (r.left, r.top, r.right - r.left, r.bottom - r.top)
            out.insert(0, item) if info.dwFlags & 1 else out.append(item)  # primary first
            return True

        callback = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC,
                                      ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)(found)
        ctypes.windll.user32.EnumDisplayMonitors(None, None, callback, 0)
        if out:
            return out
    return [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]


def load_poster(path):
    if path.lower().endswith(".pdf"):
        import pymupdf as fitz
        with fitz.open(path) as doc:
            pix = doc[0].get_pixmap(dpi=200)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return Image.open(path).convert("RGB")


def fit(image, width, height):
    scale = min(width / image.width, height / image.height)
    return image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.LANCZOS)


def parse(text):
    sections, title, body = [], None, []
    for line in text.splitlines():
        if line.startswith("# "):
            if title is not None:
                sections.append((title, "\n".join(body).strip()))
            title, body = line[2:].strip(), []
        elif title is not None:
            body.append(line)
    if title is not None:
        sections.append((title, "\n".join(body).strip()))
    return sections


def shade(color, factor):
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(min(255, int(c * factor)) for c in (r, g, b))


class Btn(tk.Label):
    """A flat colored button (macOS ignores colors on tk.Button, so this is built on a Label)."""

    def __init__(self, master, text, command, color):
        super().__init__(master, text=text, fg="white", font=(UI, 12, "bold"), padx=16, pady=8, cursor="hand2")
        self.command = command
        self.set(text, color)
        self.bind("<Button-1>", lambda e: self.config(bg=shade(self.color, 0.8)))
        self.bind("<ButtonRelease-1>", self.release)
        self.bind("<Enter>", lambda e: self.config(bg=shade(self.color, 1.15)))
        self.bind("<Leave>", lambda e: self.config(bg=self.color))

    def set(self, text, color):
        self.color = color
        self.config(text=text, bg=color)

    def release(self, event):
        self.config(bg=self.color)
        if 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.command()


class PosterCanvas(tk.Canvas):
    """A canvas that keeps an image centered and scaled to fit."""

    def __init__(self, master, **kw):
        super().__init__(master, bg="black", highlightthickness=0, **kw)
        self.image = None
        self.blank = False
        self.bind("<Configure>", lambda e: self.draw())

    def show(self, image=None, blank=None):
        if image is not None:
            self.image = image
        if blank is not None:
            self.blank = blank
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if self.blank or w < 2 or h < 2:
            return
        if self.image is None:
            self.create_text(w // 2, h // 2, text="No poster loaded", fill=MUTED, font=(UI, 12))
            return
        self.photo = ImageTk.PhotoImage(fit(self.image, w, h))
        self.create_image(w // 2, h // 2, image=self.photo)


class App:
    def __init__(self, root):
        self.root = root
        self.audience = None
        self.image = None
        self.editing = False
        self.blank = False
        self.current = 0
        self.started = None
        self.settings = self.load_settings()
        self.font_size = self.settings.get("font_size", 24)
        self.notes = open(NOTES_FILE).read() if os.path.exists(NOTES_FILE) else SAMPLE
        self.sections = parse(self.notes)

        x, y, w, h = screens(root)[0]
        root.title(TITLE)
        root.geometry(f"{min(w, 1400)}x{min(h - 80, 860)}+{x}+{y + 25}")
        root.minsize(900, 560)
        root.configure(bg=BG)
        self.build()
        self.bind_keys()

        hidden = hide_from_capture(root)
        self.hidden_label.config(text="●  Notes hidden from screen share" if hidden else "●  Could not hide notes window",
                                 fg=GOOD if hidden else BAD)
        poster = self.settings.get("poster")
        if poster and os.path.exists(poster):
            self.set_poster(poster)
        self.render()
        self.tick()
        root.lift()
        root.focus_force()

    # ---------- layout ----------

    def button(self, parent, text, command, color=BLUE):
        return Btn(parent, text, command, color)

    def build(self):
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=16, pady=(14, 10))
        tk.Label(top, text="Presenter View", bg=BG, fg=FG, font=(UI, 16, "bold")).pack(side="left")
        self.poster_name = tk.Label(top, text="", bg=BG, fg=MUTED, font=(UI, 11))
        self.poster_name.pack(side="left", padx=12)

        self.present_btn = self.button(top, "▶  Start presenting", self.toggle_present, BLUE)
        self.present_btn.pack(side="right")
        self.edit_btn = self.button(top, "Edit notes", self.toggle_edit, YELLOW)
        self.edit_btn.pack(side="right", padx=8)
        self.button(top, "Open poster", self.open_poster, YELLOW).pack(side="right")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=16)
        body.columnconfigure(0, weight=3, uniform="c")
        body.columnconfigure(1, weight=2, uniform="c")
        body.rowconfigure(0, weight=1)

        # Left: what you say
        left = tk.Frame(body, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        head = tk.Frame(left, bg=PANEL)
        head.pack(fill="x", padx=22, pady=(18, 0))
        self.counter = tk.Label(head, text="", bg=PANEL, fg=ACCENT, font=(UI, 11, "bold"))
        self.counter.pack(side="left")
        self.button(head, "A+", lambda: self.zoom(2)).pack(side="right")
        self.button(head, "A−", lambda: self.zoom(-2)).pack(side="right", padx=6)
        self.section_title = tk.Label(left, text="", bg=PANEL, fg=FG, font=(UI, 28, "bold"),
                                      anchor="w", justify="left")
        self.section_title.pack(fill="x", padx=22, pady=(6, 4))
        self.text = tk.Text(left, wrap="word", bg=PANEL, fg=FG, insertbackground=FG, relief="flat", bd=0,
                            highlightthickness=0, padx=22, pady=8, spacing1=6, spacing3=10)
        self.text.pack(fill="both", expand=True)
        self.next_frame = tk.Frame(left, bg=PANEL)
        self.next_frame.pack(fill="x", padx=22, pady=(0, 18))
        tk.Frame(self.next_frame, bg=LINE, height=1).pack(fill="x", pady=(0, 10))
        tk.Label(self.next_frame, text="NEXT", bg=PANEL, fg=MUTED, font=(UI, 10, "bold")).pack(anchor="w")
        self.next_label = tk.Label(self.next_frame, text="", bg=PANEL, fg=MUTED, font=(UI, 15), anchor="w",
                                   justify="left")
        self.next_label.pack(fill="x")

        # Right: timer, what the audience sees, sections
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")

        clock = tk.Frame(right, bg=PANEL, highlightbackground=LINE, highlightthickness=1)
        clock.pack(fill="x")
        self.timer = tk.Label(clock, text="00:00", bg=PANEL, fg=FG, font=(MONO, 34, "bold"))
        self.timer.pack(side="left", padx=18, pady=10)
        info = tk.Frame(clock, bg=PANEL)
        info.pack(side="right", padx=18)
        self.clock = tk.Label(info, text="", bg=PANEL, fg=MUTED, font=(UI, 13))
        self.clock.pack(anchor="e")
        reset = tk.Label(info, text="Reset timer", bg=PANEL, fg=ACCENT, font=(UI, 11), cursor="hand2")
        reset.pack(anchor="e")
        reset.bind("<Button-1>", lambda e: self.reset_timer())

        tk.Label(right, text="AUDIENCE SEES", bg=BG, fg=MUTED, font=(UI, 10, "bold")).pack(anchor="w", pady=(14, 6))
        self.preview = PosterCanvas(right, height=240)
        self.preview.pack(fill="x")
        self.blank_btn = self.button(right, "Black out screen  (B)", self.toggle_blank, YELLOW)
        self.blank_btn.pack(fill="x", pady=(8, 0))

        tk.Label(right, text="SECTIONS", bg=BG, fg=MUTED, font=(UI, 10, "bold")).pack(anchor="w", pady=(14, 6))
        self.section_list = tk.Frame(right, bg=BG)
        self.section_list.pack(fill="both", expand=True)

        foot = tk.Frame(self.root, bg=BG)
        foot.pack(fill="x", padx=16, pady=10)
        self.hidden_label = tk.Label(foot, text="", bg=BG, font=(UI, 11))
        self.hidden_label.pack(side="left")
        self.display_label = tk.Label(foot, text="", bg=BG, fg=MUTED, font=(UI, 11))
        self.display_label.pack(side="left", padx=18)
        tk.Label(foot, text="← →  or clicker: sections   ·   B: black out   ·   Esc: stop", bg=BG, fg=MUTED,
                 font=(UI, 11)).pack(side="right")
        self.update_display_label()

    def bind_keys(self):
        def key(fn):
            return lambda e: None if self.editing else fn()
        for k in ("<Right>", "<Down>", "<Next>", "<space>"):
            self.root.bind_all(k, key(lambda: self.go(self.current + 1)))
        for k in ("<Left>", "<Up>", "<Prior>"):
            self.root.bind_all(k, key(lambda: self.go(self.current - 1)))
        for k in ("b", "B", "."):
            self.root.bind_all(k, key(self.toggle_blank))
        self.root.bind_all("<Escape>", key(lambda: self.audience and self.toggle_present()))
        self.root.bind_all("<plus>", key(lambda: self.zoom(2)))
        self.root.bind_all("<equal>", key(lambda: self.zoom(2)))
        self.root.bind_all("<minus>", key(lambda: self.zoom(-2)))

    # ---------- poster ----------

    def open_poster(self):
        path = filedialog.askopenfilename(title="Choose your poster", filetypes=FILETYPES)
        if path:
            self.set_poster(path)

    def set_poster(self, path):
        try:
            self.image = load_poster(path)
        except Exception as e:
            self.poster_name.config(text=f"Could not open poster: {e}", fg=BAD)
            return
        self.poster_name.config(text=os.path.basename(path), fg=MUTED)
        self.settings["poster"] = path
        self.save_settings()
        self.preview.show(self.image)
        if self.audience:
            self.audience_canvas.show(self.image)

    def toggle_present(self):
        if self.audience:
            self.audience.destroy()
            self.audience = None
            self.present_btn.set("▶  Start presenting", BLUE)
            self.update_display_label()
            return
        if self.image is None:
            self.open_poster()
            if self.image is None:
                return
        self.audience = tk.Toplevel(self.root, bg="black")
        self.audience.title("Poster")
        self.audience.protocol("WM_DELETE_WINDOW", self.toggle_present)
        self.audience_canvas = PosterCanvas(self.audience)
        self.audience_canvas.pack(fill="both", expand=True)
        self.audience_canvas.show(self.image, blank=self.blank)
        self.place_audience()
        if self.started is None:
            self.started = time.time()
        self.present_btn.set("■  Stop presenting", RED)
        self.update_display_label()

    def place_audience(self):
        """Full screen on the HDMI/second display if there is one, else a normal window to share."""
        displays = screens(self.root)
        self.display_count = len(displays)
        self.audience.attributes("-fullscreen", False)
        if len(displays) > 1:
            x, y, w, h = displays[1]
            self.audience.geometry(f"{w}x{h}+{x}+{y}")
            self.audience.after(400, lambda: self.audience and self.audience.attributes("-fullscreen", True))
        else:
            x, y, w, h = displays[0]
            self.audience.geometry(f"{w // 2}x{h - 120}+{x + w // 2}+{y + 40}")
        self.root.after(900, self.focus_notes)

    def focus_notes(self):
        self.root.lift()
        self.root.focus_force()

    def toggle_blank(self):
        self.blank = not self.blank
        self.preview.show(blank=self.blank)
        if self.audience:
            self.audience_canvas.show(blank=self.blank)
        self.blank_btn.set("Show poster again  (B)" if self.blank else "Black out screen  (B)",
                           RED if self.blank else YELLOW)

    def update_display_label(self):
        n = len(screens(self.root))
        if n > 1:
            text = "HDMI / second screen: showing poster" if self.audience else "HDMI / second screen found: poster will go full screen there"
            color = GOOD
        else:
            key = "System Settings → Displays → Extend" if sys.platform == "darwin" else "press Win + P → Extend"
            text = f"One screen only. Using HDMI? Set it to Extend ({key}), not Mirror/Duplicate"
            color = YELLOW
        self.display_label.config(text=text, fg=color)
        return n

    # ---------- notes ----------

    def toggle_edit(self):
        if self.editing:
            self.notes = self.text.get("1.0", "end-1c")
            with open(NOTES_FILE, "w") as f:
                f.write(self.notes)
            self.sections = parse(self.notes)
            self.current = min(self.current, max(0, len(self.sections) - 1))
        self.editing = not self.editing
        self.edit_btn.set("Save notes" if self.editing else "Edit notes", GREEN if self.editing else YELLOW)
        self.render()

    def go(self, index):
        if self.sections:
            self.current = max(0, min(index, len(self.sections) - 1))
            self.render()

    def zoom(self, step):
        self.font_size = max(14, min(48, self.font_size + step))
        self.settings["font_size"] = self.font_size
        self.save_settings()
        self.render()

    def render(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        for w in self.section_list.winfo_children():
            w.destroy()

        if self.editing:
            self.counter.config(text="EDITING")
            self.section_title.config(text="Start each section with  # Title")
            self.text.config(font=(MONO, 15))
            self.text.insert("1.0", self.notes)
            self.next_frame.pack_forget()
            self.text.focus_set()
            return

        self.next_frame.pack(fill="x", padx=22, pady=(0, 18))
        self.text.config(font=(UI, self.font_size))
        if not self.sections:
            self.counter.config(text="")
            self.section_title.config(text="No notes yet")
            self.text.insert("1.0", 'Click "Edit notes" and start each section with "# Title".')
            self.next_label.config(text="")
        else:
            title, body = self.sections[self.current]
            self.counter.config(text=f"SECTION {self.current + 1} OF {len(self.sections)}")
            self.section_title.config(text=title)
            self.text.insert("1.0", body)
            nxt = self.sections[self.current + 1][0] if self.current + 1 < len(self.sections) else "End of presentation"
            self.next_label.config(text=nxt)
        self.text.config(state="disabled")

        for i, (title, _) in enumerate(self.sections):
            on = i == self.current
            row = tk.Label(self.section_list, text=f"  {i + 1}.  {title}", anchor="w", cursor="hand2",
                           bg=ACCENT if on else PANEL, fg=FG if on else MUTED, font=(UI, 13, "bold" if on else "normal"),
                           padx=8, pady=8)
            row.pack(fill="x", pady=(0, 4))
            row.bind("<Button-1>", lambda e, i=i: self.go(i))

    # ---------- timer & settings ----------

    def reset_timer(self):
        self.started = time.time() if self.audience else None

    def tick(self):
        self.ticks = getattr(self, "ticks", 0) + 1
        if self.ticks % 4 == 0:  # every 2 s: notice HDMI being plugged in or out
            n = self.update_display_label()
            if self.audience and n != getattr(self, "display_count", n):
                self.place_audience()
        s = int(time.time() - self.started) if self.started else 0
        self.timer.config(text=f"{s // 60:02d}:{s % 60:02d}")
        self.clock.config(text=time.strftime("%I:%M %p").lstrip("0"))
        self.root.after(500, self.tick)

    def load_settings(self):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def save_settings(self):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self.settings, f)


if __name__ == "__main__":
    if sys.platform == "win32":  # sharp text and correct screen positions on scaled displays
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
    root = tk.Tk()
    App(root)
    root.mainloop()
