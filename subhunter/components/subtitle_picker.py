import os
import tkinter
import customtkinter as ctk
from subhunter.core.theme import Theme, FONT_UI, FONT_MONO
from subhunter.core.providers import PROVIDER_INFO


LANGUAGE_NAMES = {
    "spa": "Espanol", "eng": "English", "por": "Portugues", "fra": "Francais",
    "ita": "Italiano", "deu": "Deutsch", "zho": "Chinese", "jpn": "Japanese",
    "kor": "Korean", "ara": "Arabic", "rus": "Russian",
}
VARIANT_NAMES = {("spa", "MX"): "Latino", ("spa", "ES"): "Espana", ("por", "BR"): "Brasil"}


def _language_label(language):
    country = getattr(getattr(language, "country", None), "alpha2", None)
    key = (language.alpha3, country)
    label = VARIANT_NAMES.get(key) or LANGUAGE_NAMES.get(language.alpha3, language.alpha3)
    if getattr(language, "hi", False):
        label += " (SDH)"
    return label


class SubtitlePicker(ctk.CTkToplevel):
    """Dialog to pick which subtitle/provider to download per video.

    CustomTkinter widgets are expensive (each one is a canvas), so only the top
    options per video are built up front and groups are added a few at a time.
    """

    VISIBLE = 5       # options shown per video before "show more"
    GROUPS_PER_TICK = 2

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
        self.geometry("900x560")
        self.minsize(600, 400)
        self.configure(fg_color=theme.bg_deep)

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

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
        self._scroll = scroll
        self._debounce_scrollbar(scroll)

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
            btn_frame, text="Cancelar", command=self._close,
            width=100, height=32,
            font=ctk.CTkFont(family=FONT_UI, size=12),
            fg_color=t.bg_input, hover_color=t.bg_card_hover,
            text_color=t.text, corner_radius=6,
            border_width=1, border_color=t.border,
        ).pack(side="right")

        self._pending = list(self.results.items())
        self._build_next_groups()

    @staticmethod
    def _debounce_scrollbar(scroll):
        """CTkScrollbar.set redraws and calls update_idletasks on every canvas
        change, i.e. once per widget added or removed: quadratic with many rows.
        Coalesce those into one redraw."""
        bar = scroll._scrollbar
        pending = []

        def redraw():
            pending.clear()
            if bar.winfo_exists():
                bar._draw()

        def lazy_set(start, end):
            bar._start_value, bar._end_value = float(start), float(end)
            if not pending:
                pending.append(bar.after(15, redraw))

        scroll._parent_canvas.configure(yscrollcommand=lazy_set)

    def _build_next_groups(self):
        if not self.winfo_exists():
            return
        for filepath, subs in self._pending[:self.GROUPS_PER_TICK]:
            self._build_video_group(self._scroll, self.theme, filepath, subs)
        self._pending = self._pending[self.GROUPS_PER_TICK:]
        if self._pending:
            self.after(1, self._build_next_groups)

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

        options = ctk.CTkFrame(group, fg_color="transparent")
        options.pack(fill="x")
        for i, (sub, score, provider) in enumerate(subs[:self.VISIBLE]):
            self._build_option(options, t, var, i, sub, score, provider)

        hidden = len(subs) - self.VISIBLE
        if hidden > 0:
            def show_more():
                more.destroy()
                for i, (sub, score, provider) in enumerate(subs[self.VISIBLE:], self.VISIBLE):
                    self._build_option(options, t, var, i, sub, score, provider)

            more = ctk.CTkButton(
                group, text=f"Mostrar {hidden} mas", command=show_more,
                width=110, height=20,
                font=ctk.CTkFont(family=FONT_UI, size=10),
                fg_color="transparent", hover_color=t.bg_card_hover,
                text_color=t.accent, corner_radius=4,
            )
            more.pack(anchor="w", padx=34, pady=(2, 0))

        # Small padding at bottom
        tkinter.Frame(group, height=4, bg=t.bg_card).pack()

    def _build_option(self, parent, t: Theme, var, i, sub, score, provider):
        # Plain tkinter: a CustomTkinter widget is a canvas redrawn on every
        # layout change, and dozens of rows of them froze the dialog
        bg = t.bg_card
        row = tkinter.Frame(parent, bg=bg)
        row.pack(fill="x", padx=8, pady=1)
        select = lambda _e=None: var.set(i)  # noqa: E731

        tkinter.Radiobutton(
            row, variable=var, value=i, bg=bg, activebackground=bg,
            selectcolor=t.bg_input, fg=t.accent, highlightthickness=0, bd=0,
        ).pack(side="left", padx=(4, 6))

        score_pct = max(0, min(100, int(score)))  # already a 0-100 match percentage
        score_color = t.green if score_pct > 70 else t.amber if score_pct > 40 else t.red
        release = getattr(sub, "release_info", None) or ""
        if isinstance(release, (list, tuple)):
            release = release[0] if release else ""

        cells = [
            (PROVIDER_INFO.get(provider, (provider,))[0], 16, (FONT_MONO, 10, "bold"), t.accent, "w"),
            (f"{score_pct}%", 4, (FONT_MONO, 9), score_color, "e"),
        ]
        for text, width, font, color, anchor in cells:
            lbl = tkinter.Label(row, text=text, width=width, anchor=anchor, font=font, fg=color, bg=bg)
            lbl.pack(side="left", padx=(0, 6))
            lbl.bind("<Button-1>", select)

        bar = tkinter.Canvas(row, width=80, height=6, bg=bg, highlightthickness=0)
        bar.pack(side="left", padx=(0, 8), pady=8)
        bar.create_rectangle(0, 0, 80, 6, fill=t.track, outline="")
        bar.create_rectangle(0, 0, max(2, int(80 * score_pct / 100)), 6,
                             fill=score_color, outline="")

        # Best badge for first one (blank otherwise keeps columns aligned)
        tkinter.Label(
            row, text="mejor" if i == 0 else "", width=6, font=(FONT_UI, 8),
            fg=t.bg_deep, bg=t.accent_dim if i == 0 else bg,
        ).pack(side="left", padx=(0, 6))

        # Language variant + release name, so e.g. Latino/Espana can be told apart
        cells = [
            (_language_label(sub.language), 10, (FONT_UI, 9, "bold"), t.text_mid, False),
            (str(release)[:70], 0, (FONT_UI, 9), t.text_dim, True),
        ]
        for text, width, font, color, expand in cells:
            lbl = tkinter.Label(row, text=text, width=width, anchor="w", font=font, fg=color, bg=bg)
            lbl.pack(side="left", fill="x" if expand else None, expand=expand, padx=(0, 4))
            lbl.bind("<Button-1>", select)

    def _confirm(self):
        selections = {}
        fallbacks = {}
        for filepath, (var, subs) in self._selections.items():
            idx = var.get()
            if idx < len(subs):
                selections[filepath] = subs[idx][0]  # subtitle object
                fallbacks[filepath] = subs  # all alternatives for fallback

        self._close()
        if self._on_confirm:
            self._on_confirm(selections, fallbacks)

    def _close(self):
        """Destroy without the scrollable frame redrawing its scrollbar for
        every child that goes away (quadratic, froze the app for ~30 s)."""
        self._pending = []
        self.withdraw()
        self._scroll.unbind("<Configure>")
        self._scroll._parent_canvas.configure(yscrollcommand="")
        self.destroy()
