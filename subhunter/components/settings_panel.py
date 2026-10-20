import customtkinter as ctk
from subhunter.core.theme import Theme, FONT_UI, FONT_MONO
from subhunter.core.config import Config
from subhunter.core.constants import LANGUAGES


class SettingsPanel(ctk.CTkToplevel):
    """Modal settings window."""

    def __init__(self, parent, theme: Theme, config: Config, on_save=None):
        super().__init__(parent)
        self.theme = theme
        self.config = config
        self._on_save = on_save

        self.title("Configuracion")
        self.geometry("560x640")
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
            font=ctk.CTkFont(family=FONT_UI, size=18, weight="bold"),
            text_color=t.text,
        ).pack(anchor="w", padx=pad, pady=(pad, 4))

        ctk.CTkLabel(
            self, text="Los cambios se guardan automaticamente",
            font=ctk.CTkFont(family=FONT_UI, size=10),
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
            font=ctk.CTkFont(family=FONT_UI, size=11),
            text_color=t.text_mid,
        ).pack(anchor="w", padx=12, pady=(0, 4))

        self._default_lang = ctk.StringVar(value=self.config.get("default_language"))
        ctk.CTkOptionMenu(
            scroll, values=list(LANGUAGES.keys()),
            variable=self._default_lang, width=160, height=30,
            font=ctk.CTkFont(family=FONT_UI, size=11),
            fg_color=t.bg_input, button_color=t.accent_dim,
            button_hover_color=t.accent,
            dropdown_fg_color=t.bg_card, dropdown_hover_color=t.bg_card_hover,
            dropdown_text_color=t.text, text_color=t.text, corner_radius=6,
        ).pack(anchor="w", padx=12, pady=(0, 10))

        ctk.CTkLabel(
            scroll, text="Idiomas a descargar (simultaneo)",
            font=ctk.CTkFont(family=FONT_UI, size=11),
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
                command=self._render_providers,
                font=ctk.CTkFont(family=FONT_UI, size=11),
                checkbox_width=16, checkbox_height=16,
                fg_color=t.accent, hover_color=t.accent_bright,
                border_color=t.text_dim, checkmark_color=t.bg_deep,
                text_color=t.text, width=110,
            ).pack(side="left", padx=(0, 4), pady=2)
            col += 1
            if col % 4 == 0:
                row_frame = ctk.CTkFrame(lang_grid, fg_color="transparent")
                row_frame.pack(fill="x")

        # === DESCARGA ===
        self._section(scroll, t, "Descarga")

        self._sync_var = ctk.BooleanVar(value=self.config.get("auto_sync", True))
        ctk.CTkCheckBox(
            scroll, text="Sincronizar con la pista incrustada del video (requiere ffmpeg)",
            variable=self._sync_var,
            font=ctk.CTkFont(family=FONT_UI, size=11),
            checkbox_width=16, checkbox_height=16,
            fg_color=t.accent, hover_color=t.accent_bright,
            border_color=t.text_dim, checkmark_color=t.bg_deep,
            text_color=t.text,
        ).pack(anchor="w", padx=12, pady=(0, 6))

        # === PROVEEDORES ===
        self._section(scroll, t, "Proveedores")

        self._show_all = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            scroll, text="Mostrar tambien proveedores de otros idiomas",
            variable=self._show_all, command=self._render_providers,
            font=ctk.CTkFont(family=FONT_UI, size=10),
            checkbox_width=14, checkbox_height=14,
            fg_color=t.accent_dim, hover_color=t.accent,
            border_color=t.text_dim, checkmark_color=t.bg_deep,
            text_color=t.text_dim,
        ).pack(anchor="w", padx=12, pady=(0, 6))

        self._providers_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self._providers_frame.pack(fill="x", pady=(0, 10))

        from subhunter.core.providers import (
            provider_catalog, CREDENTIAL_FIELDS, SECRET_FIELDS,
        )
        self._catalog = provider_catalog()
        self._field_labels = CREDENTIAL_FIELDS
        self._secret_fields = SECRET_FIELDS
        self._field_values = {
            p["name"]: dict(self.config.get("provider_settings", {}).get(p["name"], {}))
            for p in self._catalog
        }
        self._field_entries = {}
        for p in self._catalog:
            self._provider_vars[p["name"]] = ctk.BooleanVar(
                value=self.config.is_provider_enabled(p["name"]))
        self._render_providers()

        # === BUTTONS ===
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=pad, pady=(0, pad))

        ctk.CTkButton(
            btn_frame, text="Guardar", command=self._save,
            width=120, height=32,
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

    def _wanted_languages(self):
        names = [n for n, var in self._lang_vars.items() if var.get()]
        names.append(self._default_lang.get())
        return {LANGUAGES[n] for n in names if n in LANGUAGES}

    def _collect_fields(self):
        """Keep typed values when the list is re-rendered."""
        for (name, field), entry in self._field_entries.items():
            try:
                self._field_values.setdefault(name, {})[field] = entry.get()
            except Exception:
                pass

    def _render_providers(self):
        t = self.theme
        self._collect_fields()
        self._field_entries = {}
        for child in self._providers_frame.winfo_children():
            child.destroy()

        wanted = self._wanted_languages()
        for p in self._catalog:
            name = p["name"]
            relevant = bool(p["languages"] & wanted) or not p["languages"]
            if not (relevant or self._show_all.get() or self._provider_vars[name].get()):
                continue

            row = ctk.CTkFrame(self._providers_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=(3, 0))

            label = p["label"]
            if p["needs_config"]:
                label += "  (requiere cuenta / API key)"
            ctk.CTkCheckBox(
                row, text=label, variable=self._provider_vars[name],
                font=ctk.CTkFont(family=FONT_UI, size=11),
                checkbox_width=16, checkbox_height=16,
                fg_color=t.accent, hover_color=t.accent_bright,
                border_color=t.text_dim, checkmark_color=t.bg_deep,
                text_color=t.text,
            ).pack(anchor="w")

            if p["description"]:
                ctk.CTkLabel(
                    row, text=p["description"],
                    font=ctk.CTkFont(family=FONT_UI, size=10),
                    text_color=t.text_dim, anchor="w",
                ).pack(anchor="w", padx=(24, 0))

            for field in p["fields"]:
                line = ctk.CTkFrame(row, fg_color="transparent")
                line.pack(anchor="w", padx=(24, 0), pady=1)
                ctk.CTkLabel(
                    line, text=self._field_labels[field], width=110, anchor="w",
                    font=ctk.CTkFont(family=FONT_UI, size=10),
                    text_color=t.text_mid,
                ).pack(side="left")
                entry = ctk.CTkEntry(
                    line, width=220, height=26,
                    show="*" if field in self._secret_fields else "",
                    font=ctk.CTkFont(family=FONT_MONO, size=10),
                    fg_color=t.bg_input, border_color=t.border,
                    text_color=t.text, corner_radius=6,
                )
                entry.pack(side="left")
                value = self._field_values.get(name, {}).get(field, "")
                if value:
                    entry.insert(0, value)
                self._field_entries[(name, field)] = entry

    def _section(self, parent, t: Theme, title: str):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=0, pady=(10, 4))

        ctk.CTkLabel(
            frame, text=title,
            font=ctk.CTkFont(family=FONT_UI, size=13, weight="bold"),
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
        self._collect_fields()
        self.config.set("providers", {k: v.get() for k, v in self._provider_vars.items()})
        self.config.set("provider_settings", {
            name: {k: v.strip() for k, v in values.items() if v and v.strip()}
            for name, values in self._field_values.items()
            if any(v and v.strip() for v in values.values())
        })
        self.config.set("auto_sync", self._sync_var.get())

        self.config.save()

        if self._on_save:
            self._on_save()

        self.destroy()
