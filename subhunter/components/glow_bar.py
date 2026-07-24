from tkinter import Canvas
from subhunter.core.theme import Theme


class GlowBar(Canvas):
    """Progress bar with golden glow tip effect."""

    def __init__(self, parent, theme: Theme, height=6, **kwargs):
        self.theme = theme
        super().__init__(
            parent, height=height, bg=theme.bg_deep,
            highlightthickness=0, **kwargs
        )
        self._progress = 0.0
        self._h = height
        self.bind("<Configure>", self._draw)

    def set(self, value):
        self._progress = max(0.0, min(1.0, value))
        self._draw()

    def apply_theme(self, theme: Theme):
        self.theme = theme
        self.configure(bg=theme.bg_deep)
        self._draw()

    def _draw(self, _event=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2:
            return

        t = self.theme
        self.create_rectangle(0, 0, w, h, fill=t.track, outline="")

        if self._progress > 0:
            fw = int(w * self._progress)
            self.create_rectangle(0, 0, fw, h, fill=t.accent_dim, outline="")
            by = max(0, (h - self._h) // 2)
            self.create_rectangle(0, by, fw, by + self._h, fill=t.accent, outline="")
            tw = min(20, fw)
            self.create_rectangle(fw - tw, by, fw, by + self._h, fill=t.accent_bright, outline="")
