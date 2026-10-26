"""Voice agent window: 3D-lit glass orb, particle shell, electric arcs, live waveform.

Static art (gradient, panel) is drawn once per resize (tag "bg"); the hero area
(orb, bars, arcs) is software-rendered each frame by app.orb3d.Renderer. Tokens follow an 8px rhythm and
text/background pairs are >= 4.5:1.
"""
import math, queue, sys, threading, time, tkinter as tk
from PIL import ImageTk
from app import settings
from app.orb3d import Renderer

# --- tokens -----------------------------------------------------------------
NAVY      = "#050816"
TEAL_DEEP = "#0b9e96"
PANEL     = "#060c18"
EDGE      = "#1c5f66"
TEAL      = "#2dd4bf"
TEAL_HI   = "#99f6e4"
TEXT      = "#e6fffb"   # ~16:1 on PANEL
TEXT_DIM  = "#86adb0"   # ~7:1 on PANEL
FONT      = "Segoe UI"
S1, S2, S3 = 8, 16, 24

STATES = {   # state -> (label, orb colour, energy 0..1)
    "loading":   ("Loading models", "#2f6f73", 0.0),
    "sleeping":  (f'Standby  -  say "Hey {settings.AGENT_NAME}"', "#2f8f8a", 0.0),
    "idle":      (f"Hold {settings.PTT_KEY.title()} to talk", "#38bdf8", 0.0),
    "listening": ("Listening", TEAL, 1.0),
    "thinking":  ("Thinking", "#fbbf24", 0.4),
    "speaking":  ("Speaking", "#67e8f9", 1.0),
}
MODES = [("Voice", "wake"), ("Push to talk", "ptt"), ("Always on", "always")]


def _hex(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def _mix(a, b, t):
    """Blend colour a toward b by t (0..1): stands in for alpha on a Canvas."""
    ra, rb = _hex(a), _hex(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ra, rb))


class Pill(tk.Label):
    """Flat pill button: hover, keyboard focus ring, optional primary style."""
    def __init__(self, parent, text, command, primary=False):
        self._primary, self._cmd, self._selected = primary, command, False
        super().__init__(parent, text=text, cursor="hand2", takefocus=1,
                         font=(FONT, 10, "bold" if primary else "normal"),
                         padx=S2, pady=S1 - 2, highlightthickness=1,
                         highlightbackground=PANEL, highlightcolor=TEAL_HI)
        self._paint(False)
        self.bind("<Enter>", lambda e: self._paint(True))
        self.bind("<Leave>", lambda e: self._paint(False))
        self.bind("<Button-1>", lambda e: self._cmd())
        self.bind("<space>", lambda e: self._cmd())
        self.bind("<Return>", lambda e: self._cmd())

    def _paint(self, hover):
        if self._primary:
            self.configure(bg=TEAL_HI if hover else TEAL, fg="#03211f",
                           highlightbackground=TEAL)
        elif self._selected:
            self.configure(bg="#0f2a33", fg=TEXT, highlightbackground=EDGE)
        else:
            self.configure(bg="#0a1522" if hover else PANEL,
                           fg=TEXT if hover else TEXT_DIM,
                           highlightbackground=EDGE if hover else PANEL)

    def select(self, on):
        self._selected = on
        self._paint(False)


class App:
    def __init__(self, mode: str):
        self.q = queue.Queue()
        self.mode = mode
        self.state = "loading"
        self.colour = _hex(STATES["loading"][1])
        self.phase = 0.0
        self.level = 0.0          # smoothed mic level
        self.amp = 0.0            # smoothed waveform amplitude
        self.frame = 0
        self.geom = None
        self.renderer = None
        self.photo = None
        self.mouse = (0, 0)
        self.light = [-0.4, -0.5]

        self.root = root = tk.Tk()
        root.title(settings.AGENT_NAME)
        root.geometry("960x640")
        root.minsize(760, 540)
        root.configure(bg=NAVY)

        self.c = c = tk.Canvas(root, bg=NAVY, highlightthickness=0)
        c.pack(fill="both", expand=True)

        # header: title (left) + modes and primary action (right)
        self.title = tk.Label(c, text=settings.AGENT_NAME.upper(), bg=PANEL, fg=TEXT,
                              font=(FONT, 12, "bold"))
        self.controls = tk.Frame(c, bg=PANEL)
        self.mode_btns = {}
        for label, m in MODES:
            b = Pill(self.controls, label, lambda m=m: self._set_mode(m))
            b.pack(side="left", padx=2)
            self.mode_btns[m] = b
        self.clear_btn = Pill(self.controls, "Clear", self._clear)
        self.clear_btn.pack(side="left", padx=(S1, 2))
        self.toggle = Pill(self.controls, "Standby", self._toggle_active, primary=True)
        self.toggle.pack(side="left", padx=(S1, 0))

        # conversation
        self.logbox = tk.Frame(c, bg=PANEL)
        self.log = tk.Text(self.logbox, bg=PANEL, fg=TEXT, bd=0, wrap="word", padx=0,
                           pady=0, font=(FONT, 11), state="disabled", relief="flat",
                           highlightthickness=0, spacing1=2, spacing3=2, cursor="arrow")
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("who", font=(FONT, 9), foreground=TEXT_DIM, spacing1=S1)
        self.log.tag_config("user", foreground=TEXT_DIM)
        self.log.tag_config("assistant", foreground=TEXT)
        self.log.tag_config("system", foreground=TEXT_DIM, font=(FONT, 9, "italic"))

        c.bind("<Configure>", self._layout)
        root.bind("<Escape>", lambda e: self._set_active(False))
        root.bind("<Motion>", lambda e: setattr(self, "mouse", (e.x_root - root.winfo_rootx(), e.y_root - root.winfo_rooty())))
        self._refresh_controls()
        self._animate()
        self._poll()

    # --- layout / static art ----------------------------------------------
    def _layout(self, _=None):
        W, H = self.c.winfo_width(), self.c.winfo_height()
        if W < 50 or H < 50:
            return
        m = S3
        x0, y0, x1, y1 = m, m, W - m, H - m
        self.geom = (W, H, x0, y0, x1, y1)
        c = self.c
        c.delete("bg")
        # window gradient: navy -> teal toward the bottom
        for y in range(0, H, 4):
            t = max(0.0, (y / H - 0.45) / 0.55)
            c.create_rectangle(0, y, W, y + 4, outline="", fill=_mix(NAVY, TEAL_DEEP, t ** 1.4),
                               tags="bg")
        # rounded glass panel
        r = 24
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        c.create_polygon(pts, smooth=True, fill=PANEL, outline=EDGE, width=1, tags="bg")
        c.create_line(x0 + 80, y0, x1 - 80, y0, fill=TEAL, width=1, tags="bg")
        c.tag_lower("bg")

        # hero (3D-rendered) area: between header and conversation
        top, bot = y0 + 56, y1 - 128 - S3 - 8
        hw, hh = int(x1 - x0 - 2), int(bot - top)
        self.hero = (x0 + 1, top, hw, hh)
        if hw > 50 and hh > 50:
            self.renderer = Renderer(hw, hh, PANEL)
            self.photo = ImageTk.PhotoImage(self.renderer.base)
            c.delete("hero")
            c.create_image(x0 + 1, top, image=self.photo, anchor="nw", tags="hero")

        c.delete("win")
        c.create_window(x0 + S3, y0 + S2 + 4, window=self.title, anchor="nw", tags="win")
        c.create_window(x1 - S3, y0 + S2, window=self.controls, anchor="ne", tags="win")
        lw = min(W - 160, 680)
        c.create_window(W / 2, y1 - S2, window=self.logbox, anchor="s", width=lw,
                        height=128, tags="win")

    # --- agent thread -> UI ------------------------------------------------
    def emit(self, kind, text=""):
        self.q.put((kind, text))

    def _poll(self):
        try:
            while True:
                kind, text = self.q.get_nowait()
                if kind == "state":
                    self.state = text
                    self._refresh_controls()
                else:
                    self._append(kind, text)
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    def _append(self, kind, text):
        who = {"user": "You", "assistant": settings.AGENT_NAME}.get(kind)
        self.log.configure(state="normal")
        if who:
            self.log.insert("end", who + "\n", "who")
        self.log.insert("end", text + "\n", kind)
        self.log.configure(state="disabled")
        self.log.see("end")

    # --- controls ----------------------------------------------------------
    def _refresh_controls(self):
        for m, b in self.mode_btns.items():
            b.select(m == self.mode)
        if self.mode == "wake":
            self.toggle.configure(text="Wake" if self.state == "sleeping" else "Standby")
            if not self.toggle.winfo_ismapped():
                self.toggle.pack(side="left", padx=(S1, 0))
        else:
            self.toggle.pack_forget()

    def _set_mode(self, m):
        self.mode = m
        if m != "wake" and "app.main" in sys.modules:
            sys.modules["app.main"].session["active"] = False
        self._refresh_controls()
        stt_mod = sys.modules.get("app.stt")
        if stt_mod and hasattr(stt_mod, "interrupt"):
            stt_mod.interrupt.set()   # apply on the next turn

    def _toggle_active(self):
        self._set_active(self.state == "sleeping")

    def _set_active(self, on):
        if self.mode == "wake" and "app.main" in sys.modules and "app.stt" in sys.modules:
            sys.modules["app.main"].set_active(on)

    def _clear(self):
        if "app.llm" not in sys.modules:
            return
        from app import memory, llm
        memory.clear()
        llm.conversation_history.clear()
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    # --- animation ---------------------------------------------------------
    def _animate(self):
        t0 = time.perf_counter()
        if not self.geom or not self.renderer:
            self.root.after(33, self._animate)
            return
        W, H, x0, y0, x1, y1 = self.geom
        label, target_hex, energy = STATES.get(self.state, STATES["loading"])

        # ease colour (~250 ms)
        tgt = _hex(target_hex)
        self.colour = tuple(c + (t - c) * 0.16 for c, t in zip(self.colour, tgt))
        col = "#%02x%02x%02x" % tuple(round(c) for c in self.colour)

        mic = getattr(sys.modules.get("app.stt"), "level", 0.0)
        self.phase += 0.045
        self.frame += 1
        want = min(mic * 14, 1.0) if self.state == "listening" else 0.0
        self.level += (want - self.level) * 0.3
        if self.state == "listening":
            amp_t = max(0.12, self.level)
        elif self.state == "speaking":
            amp_t = 0.5 + 0.4 * abs(math.sin(self.phase * 5)) * (0.6 + 0.4 * math.sin(self.phase * 1.7))
        elif self.state == "thinking":
            amp_t = 0.14 + 0.1 * math.sin(self.phase * 4)
        else:
            amp_t = 0.05
        self.amp += (amp_t - self.amp) * 0.25

        # light follows the mouse (eased) so the orb feels like a lit 3D object
        hx, hy, hw, hh = self.hero
        mx, my = self.mouse
        tx = max(-1.0, min(1.0, (mx - (hx + hw / 2)) / (W / 2)))
        ty = max(-1.0, min(1.0, (my - (hy + hh / 2)) / (H / 2)))
        self.light[0] += (tx - self.light[0]) * 0.08
        self.light[1] += (ty - self.light[1]) * 0.08
        lx, ly, lz = self.light[0] * 0.9, self.light[1] * 0.9, 0.75
        n = math.sqrt(lx * lx + ly * ly + lz * lz)

        img = self.renderer.render(col, self.phase, self.amp, self.level, energy,
                                   light=(lx / n, ly / n, lz / n),
                                   tilt=0.30 + 0.25 * self.light[1])
        self.photo.paste(img)

        c = self.c
        c.delete("fx")
        c.create_text(hx + hw / 2, hy + hh - 14, text=label, fill=TEXT_DIM,
                      font=(FONT, 11), tags="fx")
        spent = int((time.perf_counter() - t0) * 1000)
        self.root.after(max(1, 30 - spent), self._animate)

    def start_agent(self):
        from app.main import run_agent

        def work():
            try:
                run_agent(self.mode, self.emit, get_mode=lambda: self.mode)
            except Exception as e:
                self.emit("system", f"Stopped: {e}")
                self.emit("state", "loading")

        threading.Thread(target=work, daemon=True).start()


def launch(mode: str = "wake"):
    app = App(mode)
    app.root.after(200, app.start_agent)
    app.root.mainloop()
