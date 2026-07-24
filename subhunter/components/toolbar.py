import customtkinter as ctk
from subhunter.core.theme import Theme
from subhunter.core.constants import LANGUAGES


class Toolbar(ctk.CTkFrame):
    """Top toolbar with action buttons, language picker, and options."""

    def __init__(self, parent, theme: Theme, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.theme = theme
        self.lang_var = ctk.StringVar(value="Espanol")
        self.rename_var = ctk.BooleanVar(value=True)

        self._on_folder = None
        self._on_files = None
        self._on_download = None

        self._build(theme)

    def on_folder(self, cb): self._on_folder = cb
    def on_files(self, cb): self._on_files = cb
    def on_download(self, cb): self._on_download = cb

    def _build(self, t: Theme):
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left")

        btn_cfg = dict(
            width=120, height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=t.bg_input, hover_color=t.bg_card_hover,
            border_width=1, border_color=t.border,
            text_color=t.text, corner_radius=6,
        )

        self._folder_btn = ctk.CTkButton(
            left, text="Carpeta", command=lambda: self._on_folder and self._on_folder(),
            **btn_cfg,
        )
        self._folder_btn.pack(side="left", padx=(0, 5))

        self._files_btn = ctk.CTkButton(
            left, text="Archivos", command=lambda: self._on_files and self._on_files(),
            **btn_cfg,
        )
        self._files_btn.pack(side="left", padx=(0, 5))

        self._sep = ctk.CTkLabel(
            left, text="|", text_color=t.border, font=ctk.CTkFont(size=14)
        )
        self._sep.pack(side="left", padx=6)

        self._lang_menu = ctk.CTkOptionMenu(
            left, values=list(LANGUAGES.keys()),
            variable=self.lang_var, width=115, height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=t.bg_input, button_color=t.accent_dim,
            button_hover_color=t.accent,
            dropdown_fg_color=t.bg_card, dropdown_hover_color=t.bg_card_hover,
            dropdown_text_color=t.text, text_color=t.text, corner_radius=6,
        )
        self._lang_menu.pack(side="left", padx=(0, 5))

        self._rename_cb = ctk.CTkCheckBox(
            left, text="Auto-renombrar", variable=self.rename_var,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            checkbox_width=16, checkbox_height=16,
            fg_color=t.accent, hover_color=t.accent_bright,
            border_color=t.text_dim, checkmark_color=t.bg_deep,
            text_color=t.text_mid,
        )
        self._rename_cb.pack(side="left", padx=(6, 0))

        self._dl_btn = ctk.CTkButton(
            self, text="Descargar",
            command=lambda: self._on_download and self._on_download(),
            width=150, height=32,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=t.accent_dim, hover_color=t.accent,
            text_color=t.bg_deep, corner_radius=6, state="disabled",
        )
        self._dl_btn.pack(side="right")

    def set_downloading(self, active: bool):
        if active:
            self._dl_btn.configure(state="disabled", text="Descargando...")
            self._folder_btn.configure(state="disabled")
            self._files_btn.configure(state="disabled")
        else:
            self._dl_btn.configure(state="normal", text="Descargar")
            self._folder_btn.configure(state="normal")
            self._files_btn.configure(state="normal")

    def set_has_items(self, has: bool):
        self._dl_btn.configure(state="normal" if has else "disabled")

    def apply_theme(self, t: Theme):
        self.theme = t
        for btn in (self._folder_btn, self._files_btn):
            btn.configure(
                fg_color=t.bg_input, hover_color=t.bg_card_hover,
                border_color=t.border, text_color=t.text,
            )
        self._sep.configure(text_color=t.border)
        self._lang_menu.configure(
            fg_color=t.bg_input, button_color=t.accent_dim,
            button_hover_color=t.accent,
            dropdown_fg_color=t.bg_card, dropdown_hover_color=t.bg_card_hover,
            dropdown_text_color=t.text, text_color=t.text,
        )
        self._rename_cb.configure(
            fg_color=t.accent, hover_color=t.accent_bright,
            border_color=t.text_dim, checkmark_color=t.bg_deep,
            text_color=t.text_mid,
        )
        self._dl_btn.configure(
            fg_color=t.accent_dim, hover_color=t.accent,
            text_color=t.bg_deep,
        )
