import os
import customtkinter as ctk
from subhunter.core.theme import Theme, FONT_UI, FONT_MONO


class SubtitlePicker(ctk.CTkToplevel):
    """Dialog to pick which subtitle/provider to download per video."""

    def __init__(self, parent, theme: Theme, results: dict, on_confirm=None):
        """
        results: dict mapping filepath -> list of (subtitle_obj, score, provider_name)
        on_confirm: callback(selections) where selections is dict filepath -> subtitle_obj
        """
        super().__init__(parent)
        self.theme = theme
        self.results = results
        self._on_confirm = on_confirm
        self._selections = {}  # filepath -> IntVar (index into results list)

        self.title("Seleccionar subtitulos")
        self.geometry("700x500")
        self.minsize(600, 400)
        self.configure(fg_color=theme.bg_deep)

        self.transient(parent)
        self.grab_set()

        self._build(theme)
        self.after(50, self.focus_force)

    def _build(self, t: Theme):
        pad = 16

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(pad, 8))

        ctk.CTkLabel(
            header, text="Subtitulos disponibles",
            font=ctk.CTkFont(family=FONT_UI, size=16, weight="bold"),
            text_color=t.text,
        ).pack(side="left")

        total_subs = sum(len(subs) for subs in self.results.values())
        total_videos = len(self.results)
        ctk.CTkLabel(
            header,
            text=f"{total_subs} opciones para {total_videos} videos",
            font=ctk.CTkFont(family=FONT_UI, size=11),
            text_color=t.text_dim,
        ).pack(side="right")

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=t.bg_surface, corner_radius=6,
            border_width=1, border_color=t.border,
            scrollbar_button_color=t.accent_dim,
            scrollbar_button_hover_color=t.accent,
        )
        scroll.pack(fill="both", expand=True, padx=pad, pady=(0, 8))

        for filepath, subs in self.results.items():
            self._build_video_group(scroll, t, filepath, subs)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=pad, pady=(0, pad))

        ctk.CTkButton(
            btn_frame, text="Descargar seleccionados", command=self._confirm,
            width=180, height=32,
            font=ctk.CTkFont(family=FONT_UI, size=12, weight="bold"),
            fg_color=t.accent_dim, hover_color=t.accent,
            text_color=t.bg_deep, corner_radius=6,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            btn_frame, text="Cancelar", command=self.destroy,
            width=100, height=32,
            font=ctk.CTkFont(family=FONT_UI, size=12),
            fg_color=t.bg_input, hover_color=t.bg_card_hover,
            text_color=t.text, corner_radius=6,
            border_width=1, border_color=t.border,
        ).pack(side="right")

    def _build_video_group(self, parent, t: Theme, filepath: str, subs: list):
        group = ctk.CTkFrame(parent, fg_color=t.bg_card, corner_radius=6,
                             border_width=1, border_color=t.border)
        group.pack(fill="x", padx=4, pady=4)

        # Video name header
        name = os.path.splitext(os.path.basename(filepath))[0]
        name = name.replace("_", " ").replace(".", " ")
        if len(name) > 70:
            name = name[:67] + "..."

        ctk.CTkLabel(
            group, text=name, anchor="w",
            font=ctk.CTkFont(family=FONT_UI, size=12, weight="bold"),
            text_color=t.text,
        ).pack(fill="x", padx=10, pady=(8, 4))

        if not subs:
            ctk.CTkLabel(
                group, text="No se encontraron subtitulos",
                font=ctk.CTkFont(family=FONT_UI, size=11),
                text_color=t.red, anchor="w",
            ).pack(fill="x", padx=10, pady=(0, 8))
            return

        # Radio buttons for each available subtitle
        var = ctk.IntVar(value=0)
        self._selections[filepath] = (var, subs)

        for i, (sub, score, provider) in enumerate(subs):
            row = ctk.CTkFrame(group, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=1)

            rb = ctk.CTkRadioButton(
                row, text="", variable=var, value=i,
                width=18, height=18,
                fg_color=t.accent, hover_color=t.accent_bright,
                border_color=t.text_dim,
            )
            rb.pack(side="left", padx=(4, 6))

            # Provider name
            ctk.CTkLabel(
                row, text=provider, width=120, anchor="w",
                font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
                text_color=t.accent,
            ).pack(side="left", padx=(0, 8))

            # Score bar
            score_pct = min(100, int(score / 10))
            score_color = t.green if score_pct > 70 else t.amber if score_pct > 40 else t.red

            ctk.CTkLabel(
                row, text=f"{score_pct}%", width=35, anchor="e",
                font=ctk.CTkFont(family=FONT_MONO, size=10),
                text_color=score_color,
            ).pack(side="left", padx=(0, 6))

            bar_bg = ctk.CTkFrame(row, height=6, width=80, fg_color=t.track, corner_radius=3)
            bar_bg.pack(side="left", padx=(0, 8), pady=8)
            bar_bg.pack_propagate(False)

            fill_w = max(2, int(80 * score_pct / 100))
            bar_fill = ctk.CTkFrame(bar_bg, height=6, width=fill_w,
                                     fg_color=score_color, corner_radius=3)
            bar_fill.pack(side="left")

            # Best badge for first one
            if i == 0:
                ctk.CTkLabel(
                    row, text="mejor", width=40,
                    font=ctk.CTkFont(family=FONT_UI, size=9),
                    text_color=t.bg_deep, fg_color=t.accent_dim,
                    corner_radius=3,
                ).pack(side="left", padx=(0, 4))

        # Small padding at bottom
        ctk.CTkFrame(group, height=4, fg_color="transparent").pack()

    def _confirm(self):
        selections = {}
        fallbacks = {}
        for filepath, (var, subs) in self._selections.items():
            idx = var.get()
            if idx < len(subs):
                selections[filepath] = subs[idx][0]  # subtitle object
                fallbacks[filepath] = subs  # all alternatives for fallback

        if self._on_confirm:
            self._on_confirm(selections, fallbacks)
        self.destroy()
