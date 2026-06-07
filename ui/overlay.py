from __future__ import annotations

import json
import tkinter as tk
import urllib.request

SNAPSHOT_URL = "http://127.0.0.1:8765/api/live/snapshot"
SETTINGS_URL = "http://127.0.0.1:8765/api/live/settings"

BG = "#081120"
FG_MAP = "#91a3c2"
FG_STAR = "#ffd16d"
FG_PASS = "#6da6ff"
FG_ACC = "#25c1e6"

PRESETS = {
    "top-left":     (10, 10),
    "top-right":    (None, 10),
    "bottom-left":  (10, None),
    "bottom-right": (None, None),
}


class PredictionOverlay:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", 0.88)
        self.root.configure(bg=BG)

        self._w, self._h = 340, 52
        self._hidden = True
        self.root.withdraw()
        self._overlay_enabled = False
        self._pos = "top-right"
        self._x = 0
        self._y = 0
        self._display = 0

        f1 = tk.Frame(self.root, bg=BG)
        f1.pack(fill="x", padx=10, pady=(6, 0))

        self.map_label = tk.Label(f1, text="", fg=FG_MAP, bg=BG, font=("Segoe UI", 9), anchor="w")
        self.map_label.pack(side="left")

        self.star_label = tk.Label(f1, text="", fg=FG_STAR, bg=BG, font=("Segoe UI", 9), anchor="e")
        self.star_label.pack(side="right")

        f2 = tk.Frame(self.root, bg=BG)
        f2.pack(fill="x", padx=10, pady=(0, 6))

        self.pass_label = tk.Label(f2, text="", fg=FG_PASS, bg=BG, font=("Segoe UI", 12, "bold"), anchor="w")
        self.pass_label.pack(side="left")

        self.acc_label = tk.Label(f2, text="", fg=FG_ACC, bg=BG, font=("Segoe UI", 12, "bold"), anchor="e")
        self.acc_label.pack(side="right")

        self._position()
        self._poll()
        self.root.mainloop()

    def _position(self) -> None:
        w, h = self._w, self._h

        if self._display > 0:
            try:
                display_idx = self._display - 1
                self.root.geometry(f"{w}x{h}+-9999+-9999")
                self.root.update_idletasks()
            except Exception:
                pass

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        if self._pos == "custom":
            x = self._x
            y = self._y
        else:
            preset = PRESETS.get(self._pos, PRESETS["top-right"])
            px, py = preset
            x = px if px is not None else sw - w - 14
            y = py if py is not None else sh - h - 14

        x = max(0, min(x, sw - w))
        y = max(0, min(y, sh - h))
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _fetch_json(self, url: str) -> dict | None:
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                return json.loads(resp.read())
        except Exception:
            return None

    def _poll(self) -> None:
        self._poll_count = getattr(self, "_poll_count", 0) + 1

        if self._poll_count % 5 == 1:
            settings = self._fetch_json(SETTINGS_URL)
            if settings is not None:
                self._overlay_enabled = bool(settings.get("overlay_enabled", False))
                new_pos = str(settings.get("overlay_position", "top-right"))
                new_x = int(settings.get("overlay_x", 0))
                new_y = int(settings.get("overlay_y", 0))
                new_display = int(settings.get("overlay_display", 0))
                if new_pos != self._pos or new_x != self._x or new_y != self._y or new_display != self._display:
                    self._pos = new_pos
                    self._x = new_x
                    self._y = new_y
                    self._display = new_display
                    self._position()

        if not self._overlay_enabled:
            if not self._hidden:
                self.root.withdraw()
                self._hidden = True
            self.root.after(2000, self._poll)
            return

        data = self._fetch_json(SNAPSHOT_URL)
        if data is None:
            if not self._hidden:
                self.root.withdraw()
                self._hidden = True
            self.root.after(2000, self._poll)
            return

        pred = data.get("prediction")
        beatmap = data.get("beatmap") or {}

        if pred:
            artist = beatmap.get("artist") or ""
            title = beatmap.get("title") or ""
            map_name = f"{artist} - {title}" if artist and title else (beatmap.get("version") or "n/a")
            self.map_label.config(text=map_name[:40])

            stars = beatmap.get("star_rating")
            self.star_label.config(text=f"\u2605 {stars:.2f}" if stars is not None else "")

            self.pass_label.config(text=f"Pass: {pred['pass_probability'] * 100:.1f}%")
            self.acc_label.config(text=f"Acc: {pred['predicted_accuracy']:.1f}%")
            if self._hidden:
                self._position()
                self.root.deiconify()
                self._hidden = False
        else:
            if not self._hidden:
                self.root.withdraw()
                self._hidden = True

        self.root.after(2000, self._poll)


if __name__ == "__main__":
    PredictionOverlay()
