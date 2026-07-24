import re
import os
import customtkinter as ctk
from subhunter.core.theme import Theme


class VideoRow(ctk.CTkFrame):
    """A single compact row representing a video file."""

    ROW_HEIGHT = 34

    def __init__(self, parent, filepath: str, theme: Theme, has_sub=False, **kwargs):
        super().__init__(parent, **kwargs)
        self.theme = theme
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.has_sub = has_sub
        self.check_var = ctk.BooleanVar(value=not has_sub)

        self.configure(
            fg_color=theme.bg_card, corner_radius=4,
            border_width=1, border_color=theme.border,
            height=self.ROW_HEIGHT,
        )
        self.pack_propagate(False)
        self._build(theme)

        if has_sub:
            self.set_status("Tiene sub", theme.green)

    def _build(self, t: Theme):
        # Accent bar
        self._accent = ctk.CTkFrame(self, width=3, fg_color=t.accent_dim, corner_radius=0)
        self._accent.pack(side="left", fill="y")

        # Checkbox
        self._cb = ctk.CTkCheckBox(
            self, text="", variable=self.check_var, width=14,
            checkbox_width=14, checkbox_height=14,
            fg_color=t.accent, hover_color=t.accent_bright,
            border_color=t.text_dim, checkmark_color=t.bg_deep,
        )
        self._cb.pack(side="left", padx=(8, 4))

        # Episode badge
        ep = self._parse_episode()
        self._badge = None
        if ep:
            self._badge = ctk.CTkLabel(
                self, text=ep,
                font=ctk.CTkFont(family="Consolas", size=10, weight="bold"),
                text_color=t.accent, fg_color=t.badge_bg,
                corner_radius=3, width=46, height=18,
            )
            self._badge.pack(side="left", padx=(0, 6))

        # Name
        display = os.path.splitext(self.filename)[0].replace("_", " ").replace(".", " ")
        if len(display) > 78:
            display = display[:75] + "..."

        self._name = ctk.CTkLabel(
            self, text=display, anchor="w",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=t.text,
        )
        self._name.pack(side="left", fill="x", expand=True, padx=(0, 6))

        # Status dot + label (no extra frame)
        self._status_text = ctk.CTkLabel(
            self, text="Pendiente", width=85, anchor="e",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=t.text_dim,
        )
        self._status_text.pack(side="right", padx=(0, 8))

        self._dot = ctk.CTkLabel(
            self, text="", width=6, height=6,
            fg_color=t.text_dim, corner_radius=3,
        )
        self._dot.pack(side="right", padx=(0, 4))

    def _parse_episode(self):
        m = re.search(r'[Ss](\d{2})[Ee](\d{2})', self.filename)
        return f"S{m.group(1)}E{m.group(2)}" if m else None

    def set_status(self, text: str, color: str):
        self._status_text.configure(text=text, text_color=color)
        self._dot.configure(fg_color=color)
        self._accent.configure(fg_color=color)

    def apply_theme(self, theme: Theme):
        self.theme = theme
        self.configure(fg_color=theme.bg_card, border_color=theme.border)
        self._cb.configure(
            fg_color=theme.accent, hover_color=theme.accent_bright,
            border_color=theme.text_dim, checkmark_color=theme.bg_deep,
        )
        self._name.configure(text_color=theme.text)
        self._status_text.configure(text_color=theme.text_dim)
        if self._badge:
            self._badge.configure(text_color=theme.accent, fg_color=theme.badge_bg)
