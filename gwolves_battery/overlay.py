"""Borderless always-on-top overlay window."""
import threading
import tkinter as tk
import tkinter.font as tkfont

from . import config as cfgmod
from .protocol import read_battery

# Key colour Windows renders fully transparent.
TRANSPARENT_KEY = "#010203"

STYLES = ("pill", "ring", "minimal")


class Overlay(object):
    def __init__(self, cfg, config_path=None):
        self.cfg = cfg
        self.config_path = config_path
        self.state = {"percent": None, "charging": False}
        self._lock = threading.Lock()
        self._wake = threading.Event()

        overlay = cfg["overlay"]
        self.root = tk.Tk()
        self.root.title("Mouse battery")
        self.root.overrideredirect(True)
        if overlay.get("always_on_top", True):
            self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", TRANSPARENT_KEY)
        self.root.attributes("-alpha", self._clamp_opacity(overlay["opacity"]))
        self.root.configure(bg=TRANSPARENT_KEY)
        self.root.geometry("+%d+%d" % (int(overlay["x"]), int(overlay["y"])))

        self.canvas = tk.Canvas(self.root, bg=TRANSPARENT_KEY,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self.canvas.bind("<Button-3>", self._popup)

        self._build_menu()
        threading.Thread(target=self._poll_loop, daemon=True).start()
        self._draw()
        self._tick()

    # ------------------------------------------------------------- helpers

    @staticmethod
    def _clamp_opacity(value):
        try:
            return min(1.0, max(0.1, float(value)))
        except (TypeError, ValueError):
            return 0.92

    def _persist(self):
        if self.config_path is not False:
            cfgmod.save(self.cfg, self.config_path)

    def _colors(self):
        return self.cfg["colors"]

    def _font(self, scale=1.0):
        overlay = self.cfg["overlay"]
        return tkfont.Font(family=overlay.get("font_family", "Segoe UI"),
                           size=max(7, int(int(overlay["font_size"]) * scale)),
                           weight="bold")

    # --------------------------------------------------------- interaction

    def _build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Refresh now", command=self._wake.set)
        self.menu.add_separator()

        style_menu = tk.Menu(self.menu, tearoff=0)
        for key, label in (("pill", "Pill (icon + %)"),
                           ("ring", "Ring"),
                           ("minimal", "Minimal (text only)")):
            style_menu.add_command(
                label=label, command=lambda v=key: self._set("style", v))
        self.menu.add_cascade(label="Style", menu=style_menu)

        size_menu = tk.Menu(self.menu, tearoff=0)
        for size in (14, 16, 20, 26, 34, 44):
            size_menu.add_command(
                label="%d px" % size,
                command=lambda v=size: self._set("font_size", v))
        self.menu.add_cascade(label="Size", menu=size_menu)

        alpha_menu = tk.Menu(self.menu, tearoff=0)
        for value in (1.0, 0.92, 0.8, 0.65, 0.5):
            alpha_menu.add_command(
                label="%d %%" % int(value * 100),
                command=lambda v=value: self._set_opacity(v))
        self.menu.add_cascade(label="Opacity", menu=alpha_menu)

        self.menu.add_separator()
        self.menu.add_command(label="Quit", command=self.root.destroy)

    def _popup(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _drag_start(self, event):
        self._off = (event.x_root - self.root.winfo_x(),
                     event.y_root - self.root.winfo_y())

    def _drag_move(self, event):
        x = event.x_root - self._off[0]
        y = event.y_root - self._off[1]
        self.root.geometry("+%d+%d" % (x, y))
        self.cfg["overlay"]["x"], self.cfg["overlay"]["y"] = x, y
        self._persist()

    def _set(self, key, value):
        self.cfg["overlay"][key] = value
        self._persist()
        self._draw()

    def _set_opacity(self, value):
        self.cfg["overlay"]["opacity"] = value
        self.root.attributes("-alpha", self._clamp_opacity(value))
        self._persist()

    # ------------------------------------------------------------- polling

    def _poll_loop(self):
        while True:
            try:
                status = read_battery(self.cfg)
            except Exception:
                status = None
            with self._lock:
                if status is None:
                    self.state["percent"] = None
                else:
                    self.state["percent"] = status.percent
                    self.state["charging"] = status.charging
            interval = max(5, int(self.cfg["polling"]["interval_seconds"]))
            self._wake.wait(timeout=interval)
            self._wake.clear()

    def _tick(self):
        self._draw()
        self.root.after(1000, self._tick)

    # ---------------------------------------------------------- primitives

    def _round_rect(self, x1, y1, x2, y2, radius, **kw):
        pts = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
               x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
               x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def _bolt(self, cx, cy, height):
        """Vector lightning bolt: avoids tofu boxes when no emoji font exists."""
        width = height * 0.62
        norm = [(0.52, 0.0), (0.12, 0.56), (0.40, 0.56), (0.28, 1.0),
                (0.88, 0.42), (0.58, 0.42), (0.74, 0.0)]
        x0, y0 = cx - width / 2.0, cy - height / 2.0
        pts = []
        for nx, ny in norm:
            pts += [x0 + nx * width, y0 + ny * height]
        return self.canvas.create_polygon(pts, fill=self._colors()["charging"],
                                          outline="")

    # -------------------------------------------------------------- render

    def _draw(self):
        with self._lock:
            pct = self.state["percent"]
            charging = self.state["charging"]
        self.canvas.delete("all")
        style = self.cfg["overlay"].get("style", "pill")
        {"ring": self._draw_ring,
         "minimal": self._draw_minimal}.get(style, self._draw_pill)(pct, charging)

    def _draw_pill(self, pct, charging):
        colors = self._colors()
        size = int(self.cfg["overlay"]["font_size"])
        font = self._font()
        label = "--%" if pct is None else "%d%%" % pct
        text_w = font.measure(label)
        text_h = font.metrics("linespace")

        cell_h = max(9, int(text_h * 0.60))
        cell_w = int(cell_h * 1.95)
        nub = max(2, cell_h // 5)
        gap = max(7, size // 3)
        padx, pady = max(11, size // 2), max(6, size // 3)

        width = padx * 2 + cell_w + nub + gap + text_w
        height = pady * 2 + max(text_h, cell_h)
        self.canvas.config(width=width, height=height)

        self._round_rect(0, 0, width - 1, height - 1, min(height // 2, 20),
                         fill=colors["background"], outline=colors["border"])

        bx, by = padx, (height - cell_h) // 2
        self._round_rect(bx, by, bx + cell_w, by + cell_h, 3,
                         fill=colors["cell_background"],
                         outline=colors["cell_border"])
        self.canvas.create_rectangle(bx + cell_w + 1, int(by + cell_h * 0.30),
                                     bx + cell_w + nub, int(by + cell_h * 0.70),
                                     fill=colors["cell_border"], outline="")
        if pct:
            filled = int((cell_w - 4) * pct / 100.0)
            if filled >= 2:
                self._round_rect(bx + 2, by + 2, bx + 2 + filled,
                                 by + cell_h - 2, 2,
                                 fill=cfgmod.level_color(pct, colors),
                                 outline="")
        # The cell is large enough to carry a glyph, so this style keeps the
        # bolt; only the ring signals charging through colour.
        if charging:
            self._bolt(bx + cell_w / 2.0, height / 2.0, cell_h * 1.15)

        self.canvas.create_text(bx + cell_w + nub + gap, height // 2,
                                text=label, font=font, fill=colors["text"],
                                anchor="w")

    def _draw_ring(self, pct, charging):
        colors = self._colors()
        size = int(self.cfg["overlay"]["font_size"])
        diameter = int(size * 4.0)
        thick = max(4, int(size * 0.40))
        pad = 5
        side = diameter + pad * 2
        self.canvas.config(width=side, height=side)

        self.canvas.create_oval(0, 0, side - 1, side - 1,
                                fill=colors["background"],
                                outline=colors["border"])
        box = (pad + thick // 2, pad + thick // 2,
               side - pad - thick // 2, side - pad - thick // 2)
        self.canvas.create_arc(*box, start=90, extent=-359.9, style="arc",
                               width=thick, outline=colors["track"])
        if pct:
            self.canvas.create_arc(*box, start=90, extent=-359.9 * pct / 100.0,
                                   style="arc", width=thick,
                                   outline=cfgmod.status_color(pct, charging,
                                                               colors))

        self.canvas.create_text(side // 2, side // 2,
                                text="--" if pct is None else str(pct),
                                font=self._font(0.85), fill=colors["text"])

    def _draw_minimal(self, pct, charging):
        colors = self._colors()
        size = int(self.cfg["overlay"]["font_size"])
        font = self._font()
        text = "--%" if pct is None else "%d%%" % pct
        pad = max(3, size // 6)
        text_w = font.measure(text)
        text_h = font.metrics("linespace")
        width = text_w + pad * 2 + (int(size * 0.7) if charging else 0)
        height = text_h + pad * 2
        self.canvas.config(width=width, height=height)

        # Dark outline: readable on light and dark backgrounds alike.
        for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (1, -1), (-1, 1), (1, 1)):
            self.canvas.create_text(pad + ox, pad + oy, text=text, font=font,
                                    fill=colors["outline"], anchor="nw")
        self.canvas.create_text(pad, pad, text=text, font=font,
                                fill=cfgmod.level_color(pct, colors),
                                anchor="nw")
        if charging:
            self._bolt(pad + text_w + size * 0.35, height / 2.0, text_h * 0.78)

    def run(self):
        self.root.mainloop()
