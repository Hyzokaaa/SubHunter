import customtkinter as ctk
from subhunter.core.theme import Theme
from subhunter.core.config import Config, PROVIDER_LABELS
from subhunter.core.constants import LANGUAGES


class SettingsPanel(ctk.CTkToplevel):
    """Modal settings window."""

    def __init__(self, parent, theme: Theme, config: Config, on_save=None):
        super().__init__(parent)
        self.theme = theme
        self.config = config
        self._on_save = on_save

        self.title("Configuracion")
        self.geometry("480x520")
        self.minsize(420, 480)
        self.resizable(True, True)
        self.configure(fg_color=theme.bg_deep)

        self.transient(parent)
        self.grab_set()

        self._provider_vars = {}
        self._lang_vars = {}
        self._build(theme)
        self.after(50, self.focus_force)

    def _build(self, t: Theme):
        pad = 20

        # Title
        ctk.CTkLabel(
            self, text="Configuracion",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=t.text,
        ).pack(anchor="w", padx=pad, pady=(pad, 4))

        ctk.CTkLabel(
            self, text="Los cambios se guardan automaticamente",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=t.text_dim,
        ).pack(anchor="w", padx=pad, pady=(0, 12))

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=t.bg_surface, corner_radius=6,
            border_width=1, border_color=t.border,
            scrollbar_button_color=t.accent_dim,
            scrollbar_button_hover_color=t.accent,
        )
        scroll.pack(fill="both", expand=True, padx=pad, pady=(0, 10))

        # === IDIOMAS ===
        self._section(scroll, t, "Idiomas")

        ctk.CTkLabel(
            scroll, text="Idioma por defecto",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=t.text_mid,
        ).pack(anchor="w", padx=12, pady=(0, 4))

        self._default_lang = ctk.StringVar(value=self.config.get("default_language"))
        ctk.CTkOptionMenu(
            scroll, values=list(LANGUAGES.keys()),
            variable=self._default_lang, width=160, height=30,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=t.bg_input, button_color=t.accent_dim,
            button_hover_color=t.accent,
            dropdown_fg_color=t.bg_card, dropdown_hover_color=t.bg_card_hover,
            dropdown_text_color=t.text, text_color=t.text, corner_radius=6,
        ).pack(anchor="w", padx=12, pady=(0, 10))

        ctk.CTkLabel(
            scroll, text="Idiomas a descargar (simultaneo)",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=t.text_mid,
        ).pack(anchor="w", padx=12, pady=(0, 4))

        active_langs = self.config.get("languages", ["Espanol"])
        lang_grid = ctk.CTkFrame(scroll, fg_color="transparent")
        lang_grid.pack(fill="x", padx=12, pady=(0, 10))

        col = 0
        row_frame = ctk.CTkFrame(lang_grid, fg_color="transparent")
        row_frame.pack(fill="x")
        for name in LANGUAGES:
            var = ctk.BooleanVar(value=name in active_langs)
            self._lang_vars[name] = var
            ctk.CTkCheckBox(
                row_frame, text=name, variable=var,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                checkbox_width=16, checkbox_height=16,
                fg_color=t.accent, hover_color=t.accent_bright,
                border_color=t.text_dim, checkmark_color=t.bg_deep,
                text_color=t.text, width=110,
            ).pack(side="left", padx=(0, 4), pady=2)
            col += 1
            if col % 4 == 0:
                row_frame = ctk.CTkFrame(lang_grid, fg_color="transparent")
                row_frame.pack(fill="x")

        # === PROVEEDORES ===
        self._section(scroll, t, "Proveedores")

        providers = self.config.get("providers", {})
        for key, label in PROVIDER_LABELS.items():
            var = ctk.BooleanVar(value=providers.get(key, True))
            self._provider_vars[key] = var
            ctk.CTkCheckBox(
                scroll, text=label, variable=var,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                checkbox_width=16, checkbox_height=16,
                fg_color=t.accent, hover_color=t.accent_bright,
                border_color=t.text_dim, checkmark_color=t.bg_deep,
                text_color=t.text,
            ).pack(anchor="w", padx=12, pady=2)

        # === CREDENCIALES ===
        self._section(scroll, t, "Credenciales OpenSubtitles.com")

        ctk.CTkLabel(
            scroll, text="Opcional — cuenta gratis = 20 descargas/dia",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=t.text_dim,
        ).pack(anchor="w", padx=12, pady=(0, 6))

        input_cfg = dict(
            width=260, height=30,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=t.bg_input, border_color=t.border,
            text_color=t.text, corner_radius=6,
        )

        ctk.CTkLabel(
            scroll, text="Usuario",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=t.text_mid,
        ).pack(anchor="w", padx=12, pady=(0, 2))

        self._user_entry = ctk.CTkEntry(
            scroll, placeholder_text="tu_usuario", **input_cfg,
        )
        self._user_entry.pack(anchor="w", padx=12, pady=(0, 6))
        saved_user = self.config.get("opensubtitlescom_username", "")
        if saved_user:
            self._user_entry.insert(0, saved_user)

        ctk.CTkLabel(
            scroll, text="Contrasena",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=t.text_mid,
        ).pack(anchor="w", padx=12, pady=(0, 2))

        self._pass_entry = ctk.CTkEntry(
            scroll, placeholder_text="tu_contrasena", show="*", **input_cfg,
        )
        self._pass_entry.pack(anchor="w", padx=12, pady=(0, 12))
        saved_pass = self.config.get("opensubtitlescom_password", "")
        if saved_pass:
            self._pass_entry.insert(0, saved_pass)

        # === BUTTONS ===
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=pad, pady=(0, pad))

        ctk.CTkButton(
            btn_frame, text="Guardar", command=self._save,
            width=120, height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=t.accent_dim, hover_color=t.accent,
            text_color=t.bg_deep, corner_radius=6,
        ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            btn_frame, text="Cancelar", command=self.destroy,
            width=100, height=32,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            fg_color=t.bg_input, hover_color=t.bg_card_hover,
            text_color=t.text, corner_radius=6,
            border_width=1, border_color=t.border,
        ).pack(side="right")

    def _section(self, parent, t: Theme, title: str):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=0, pady=(10, 4))

        ctk.CTkLabel(
            frame, text=title,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=t.accent,
        ).pack(side="left", padx=12)

        ctk.CTkFrame(
            frame, height=1, fg_color=t.border,
        ).pack(side="left", fill="x", expand=True, padx=(6, 12), pady=1)

    def _save(self):
        # Languages
        self.config.set("default_language", self._default_lang.get())
        active_langs = [name for name, var in self._lang_vars.items() if var.get()]
        if not active_langs:
            active_langs = [self._default_lang.get()]
        self.config.set("languages", active_langs)

        # Providers
        providers = {k: v.get() for k, v in self._provider_vars.items()}
        if not any(providers.values()):
            providers["opensubtitles"] = True
        self.config.set("providers", providers)

        # Credentials
        self.config.set("opensubtitlescom_username", self._user_entry.get().strip())
        self.config.set("opensubtitlescom_password", self._pass_entry.get().strip())

        self.config.save()

        if self._on_save:
            self._on_save()

        self.destroy()
