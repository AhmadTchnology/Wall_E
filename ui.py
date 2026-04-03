import os, json, time, math, random, threading
import tkinter as tk
from collections import deque
import sys
from pathlib import Path


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR   = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

# ── Pixel Face Palette (NO PURPLE) ──
C_BG      = "#0a0a0a"
C_PRI     = "#00d4ff"   # Cyan accent
C_ACC     = "#ffae00"   # Warm orange accent
C_SYS     = "#00ff88"   # System green
C_TEXT    = "#c8c8c8"
C_DIM     = "#1a1a1a"
C_PANEL   = "#111111"
C_RED     = "#ff3333"
C_DOT     = "#00d4ff"   # Eye pixel color (idle)
C_DOT_SPK = "#ffae00"   # Eye pixel color (speaking)


# ── Pixel grid helpers ──
PX = 6  # base pixel block size


class WallEUI:
    """Minimal pixel-art face UI for Wall-E AI Assistant."""

    def __init__(self, face_path=None, size=None):
        self.root = tk.Tk()
        self.root.title("Wall-E")
        self.root.resizable(False, False)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        W  = min(sw, 520)
        H  = min(sh, 520)
        self.root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")
        self.root.configure(bg=C_BG)

        self.W = W
        self.H = H

        # ── State ──
        self.speaking     = False
        self.tick         = 0
        self.blink_timer  = 0
        self.is_blinking  = False
        self.mouth_phase  = 0.0
        self.status_text  = "INITIALISING"

        # ── Typing queue (preserves original API) ──
        self.typing_queue = deque()
        self.is_typing    = False

        # ── Main canvas (face area) ──
        face_h = H - 90  # leave 90px for transcript bar
        self.canvas = tk.Canvas(
            self.root, width=W, height=face_h,
            bg=C_BG, highlightthickness=0,
        )
        self.canvas.place(x=0, y=0)

        # ── Transcript bar (bottom rectangle) ──
        bar_y = face_h
        bar_h = 90
        self.bar_frame = tk.Frame(
            self.root, bg=C_PANEL,
            highlightbackground=C_PRI,
            highlightcolor=C_PRI,
            highlightthickness=1,
        )
        self.bar_frame.place(x=0, y=bar_y, width=W, height=bar_h)

        self.log_text = tk.Text(
            self.bar_frame, fg=C_TEXT, bg=C_PANEL,
            insertbackground=C_PRI, borderwidth=0,
            wrap="word", font=("Courier", 9, "bold"),
            padx=10, pady=6,
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")
        self.log_text.tag_config("you", foreground="#ffffff")
        self.log_text.tag_config("ai",  foreground=C_PRI)
        self.log_text.tag_config("sys", foreground=C_SYS)

        # ── API key gate ──
        self._api_key_ready = self._api_keys_exist()
        if not self._api_key_ready:
            self._show_setup_ui()

        self._animate()
        self.root.protocol("WM_DELETE_WINDOW", lambda: os._exit(0))

    # ──────────────────────────────────────────────
    #  Animation loop
    # ──────────────────────────────────────────────
    def _animate(self):
        self.tick += 1

        # Blink logic: blink every ~3-5 seconds for 8 frames
        if not self.is_blinking:
            self.blink_timer += 1
            if self.blink_timer > random.randint(180, 300):
                self.is_blinking = True
                self.blink_timer = 0
        else:
            self.blink_timer += 1
            if self.blink_timer > 8:
                self.is_blinking = False
                self.blink_timer = 0

        # Mouth animation phase
        if self.speaking:
            self.mouth_phase += 0.35
        else:
            self.mouth_phase += 0.06

        self._draw()
        self.root.after(33, self._animate)  # ~30 FPS

    # ──────────────────────────────────────────────
    #  Pixel drawing helpers
    # ──────────────────────────────────────────────
    def _px_rect(self, gx, gy, color, px=PX):
        """Draw a single pixel block at grid coordinates."""
        x = gx * px
        y = gy * px
        self.canvas.create_rectangle(
            x, y, x + px, y + px,
            fill=color, outline="", width=0,
        )

    def _draw_pixel_grid(self, grid, ox, oy, color, px=PX):
        """Draw a 2D boolean grid as pixel blocks.
        grid: list of strings, '#' = filled pixel.
        """
        for row_i, row in enumerate(grid):
            for col_i, ch in enumerate(row):
                if ch == "#":
                    self._px_rect(ox + col_i, oy + row_i, color, px)

    # ──────────────────────────────────────────────
    #  Main draw
    # ──────────────────────────────────────────────
    def _draw(self):
        c = self.canvas
        W = self.W
        face_h = self.H - 90
        c.delete("all")

        # ── Subtle scanlines ──
        for y in range(0, face_h, 4):
            c.create_line(0, y, W, y, fill="#0d0d0d", width=1)

        # ── Calculate face center ──
        cx = W // 2
        cy = face_h // 2 - 10

        # Pixel size for face
        px = max(PX, int(min(W, face_h) / 65))

        # ── Bounce animation while speaking ──
        bounce = 0
        if self.speaking:
            bounce = int(math.sin(self.tick * 0.25) * 2)

        # Status-based eye color
        if self.speaking:
            eye_color = C_DOT_SPK
        elif self.status_text in ("PROCESSING", "RESPONDING"):
            eye_color = C_SYS
        elif self.status_text == "EXECUTING":
            eye_color = C_RED
        else:
            eye_color = C_DOT

        # ────────────────────────────
        #  EYES  (dot style, 3x3 px each)
        # ────────────────────────────
        eye_w = 3  # pixels wide
        eye_h = 1 if self.is_blinking else 3  # squish when blinking
        eye_gap = 10  # pixel gap between eyes
        eye_oy = cy // px + bounce - 2

        left_eye_ox  = cx // px - eye_gap // 2 - eye_w
        right_eye_ox = cx // px + eye_gap // 2

        # Pupil shift when speaking (looking around)
        pupil_shift = 0
        if self.speaking:
            pupil_shift = int(math.sin(self.tick * 0.15) * 2)

        for dy in range(eye_h):
            for dx in range(eye_w):
                # Left eye
                self._px_rect(
                    left_eye_ox + dx + pupil_shift,
                    eye_oy + dy + (1 if self.is_blinking else 0),
                    eye_color, px,
                )
                # Right eye
                self._px_rect(
                    right_eye_ox + dx + pupil_shift,
                    eye_oy + dy + (1 if self.is_blinking else 0),
                    eye_color, px,
                )

        # ── Eyebrow pixels (small 5px line above each eye) ──
        if not self.is_blinking:
            # Eyebrow tilt when speaking (inner raised = excited)
            brow_tilt = -1 if self.speaking else 0
            for dx in range(eye_w + 2):
                tilt = brow_tilt if dx >= (eye_w + 2) // 2 else 0
                # Left eyebrow
                self._px_rect(
                    left_eye_ox + dx - 1 + pupil_shift,
                    eye_oy - 2 + tilt,
                    C_DIM if not self.speaking else eye_color, px,
                )
                # Right eyebrow  
                tilt_r = brow_tilt if dx < (eye_w + 2) // 2 else 0
                self._px_rect(
                    right_eye_ox + dx - 1 + pupil_shift,
                    eye_oy - 2 + tilt_r,
                    C_DIM if not self.speaking else eye_color, px,
                )

        # ────────────────────────────
        #  MOUTH  (pixel style)
        # ────────────────────────────
        mouth_oy = eye_oy + 7
        mouth_cx = cx // px

        if self.speaking:
            # Speaking: animated open/close mouth (width varies)
            open_amount = int(abs(math.sin(self.mouth_phase)) * 3) + 1
            mouth_w = 5 + int(abs(math.sin(self.mouth_phase * 0.7)) * 3)
            half_w = mouth_w // 2

            # Top lip
            for dx in range(-half_w, half_w + 1):
                self._px_rect(mouth_cx + dx, mouth_oy, eye_color, px)

            # Mouth interior (dark opening)
            for dy in range(1, open_amount + 1):
                for dx in range(-half_w + 1, half_w):
                    self._px_rect(mouth_cx + dx, mouth_oy + dy, "#000000", px)
                # Side walls
                self._px_rect(mouth_cx - half_w, mouth_oy + dy, eye_color, px)
                self._px_rect(mouth_cx + half_w, mouth_oy + dy, eye_color, px)

            # Bottom lip
            for dx in range(-half_w, half_w + 1):
                self._px_rect(mouth_cx + dx, mouth_oy + open_amount + 1, eye_color, px)

        elif self.status_text in ("PROCESSING", "RESPONDING"):
            # Thinking: animated wave dots
            for i in range(7):
                wave = int(math.sin(self.mouth_phase + i * 0.8) * 1)
                self._px_rect(
                    mouth_cx - 3 + i,
                    mouth_oy + 1 + wave,
                    C_SYS if (self.tick // 6 + i) % 3 == 0 else C_DIM, px,
                )

        elif self.status_text == "EXECUTING":
            # Executing: rapid flickering bar
            flicker = self.tick % 4 < 2
            color = C_SYS if flicker else C_DIM
            for dx in range(-4, 5):
                self._px_rect(mouth_cx + dx, mouth_oy + 1, color, px)

        else:
            # Idle / Listening: small calm line (slight pulse)
            pulse = 3 + int(math.sin(self.tick * 0.04) * 1)
            for dx in range(-pulse, pulse + 1):
                self._px_rect(mouth_cx + dx, mouth_oy + 1, C_DIM, px)

        # ── Status dot (top-right corner) ──
        dot_r = 4
        dot_x = W - 16
        dot_y = 16
        if self.speaking:
            dot_col = C_ACC
        elif self.status_text in ("PROCESSING", "RESPONDING"):
            dot_col = C_SYS
        elif self.status_text == "EXECUTING":
            dot_col = C_RED
        else:
            # Blink the dot slowly
            dot_col = C_PRI if self.tick % 60 < 40 else C_BG
        c.create_oval(
            dot_x - dot_r, dot_y - dot_r,
            dot_x + dot_r, dot_y + dot_r,
            fill=dot_col, outline="",
        )

        # ── Tiny "WALL·E" label bottom-left above transcript ──
        c.create_text(
            10, face_h - 8,
            text="WALL·E", fill="#222222",
            font=("Courier", 7), anchor="sw",
        )

    # ──────────────────────────────────────────────
    #  Public API  (unchanged signatures for main.py compat)
    # ──────────────────────────────────────────────
    def write_log(self, text: str):
        tl = text.lower()
        if tl.startswith("you:"):
            self.status_text = "PROCESSING"
            tag = "you"
            clean_text = text[4:].strip()
        elif tl.startswith("ai:") or tl.startswith("wall-e:"):
            self.status_text = "RESPONDING"
            tag = "ai"
            clean_text = text[7:].strip()
        else:
            self.status_text = "EXECUTING"
            tag = "sys"
            clean_text = text

        self.typing_queue.append((clean_text, tag, True))
        if not self.is_typing:
            self._start_typing()

    def append_log(self, text: str):
        self.typing_queue.append((text, "ai", False))
        self.status_text = "RESPONDING"
        if not self.is_typing:
            self._start_typing()

    def _start_typing(self):
        if not self.typing_queue:
            self.is_typing = False
            if not self.speaking:
                self.status_text = "ONLINE"
            return

        self.is_typing = True
        text, tag, needs_prefix = self.typing_queue.popleft()

        self.log_text.configure(state="normal")

        # Keep only last ~500 chars to prevent memory buildup
        content = self.log_text.get("1.0", tk.END)
        if len(content) > 600:
            self.log_text.delete("1.0", f"end - 600 chars")

        if needs_prefix:
            prefix = "\n> " if tag == "you" else "\n>> " if tag == "ai" else "\n-- "
            if content.strip():
                pass
            self.log_text.insert(tk.END, prefix, tag)

        self._type_char(text, 0, tag)

    def _type_char(self, text, i, tag):
        if i < len(text):
            self.log_text.insert(tk.END, text[i], tag)
            self.log_text.see(tk.END)
            self.root.after(4, self._type_char, text, i + 1, tag)
        else:
            self.log_text.configure(state="disabled")
            self.root.after(10, self._start_typing)

    def start_speaking(self):
        self.speaking     = True
        self.status_text  = "SPEAKING"

    def stop_speaking(self):
        self.speaking     = False
        self.status_text  = "ONLINE"

    # ──────────────────────────────────────────────
    #  API Key Setup  (identical contract)
    # ──────────────────────────────────────────────
    def _api_keys_exist(self):
        if not API_FILE.exists():
            return False
        try:
            with open(API_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                key = data.get("gemini_api_key", "").strip()
                return bool(key)
        except Exception:
            return False

    def wait_for_api_key(self):
        while not self._api_key_ready:
            time.sleep(0.1)

    def _show_setup_ui(self):
        self.setup_frame = tk.Frame(
            self.root, bg=C_BG,
            highlightbackground=C_ACC,
            highlightcolor=C_ACC,
            highlightthickness=2,
        )
        self.setup_frame.place(relx=0.5, rely=0.5, anchor="center", width=420, height=200)

        tk.Label(
            self.setup_frame, text="API KEY REQUIRED",
            fg=C_ACC, bg=C_BG, font=("Courier", 14, "bold"),
        ).pack(pady=(16, 6))
        tk.Label(
            self.setup_frame, text="Enter Gemini API key:",
            fg=C_PRI, bg=C_BG, font=("Courier", 9, "bold"),
        ).pack(pady=(0, 12))

        self.gemini_entry = tk.Entry(
            self.setup_frame, width=44, fg=C_BG, bg=C_PRI,
            insertbackground=C_BG, borderwidth=0,
            font=("Courier", 11, "bold"), show="*",
        )
        self.gemini_entry.pack(pady=(0, 14), ipady=4)

        tk.Button(
            self.setup_frame, text="[ OK ]",
            command=self._save_api_keys, bg=C_ACC, fg=C_BG,
            activebackground=C_PRI, activeforeground=C_BG,
            font=("Courier", 12, "bold"),
            borderwidth=0, cursor="hand2",
        ).pack(pady=4, ipadx=16)

    def _save_api_keys(self):
        gemini = self.gemini_entry.get().strip()
        if not gemini:
            return
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(API_FILE, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": gemini}, f, indent=4)
        self.setup_frame.destroy()
        self._api_key_ready = True
        self.status_text = "ONLINE"
        self.write_log("SYS: Wall-E online.")