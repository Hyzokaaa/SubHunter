import os
import sys
import customtkinter as ctk
from tkinter import filedialog, messagebox, PhotoImage

from subhunter.core.theme import DARK, LIGHT
from subhunter.core.constants import LANGUAGES
from subhunter.core.config import Config
from subhunter.core.downloader import SubtitleDownloader
from subhunter.core.updater import Updater, VERSION
from subhunter.components import GlowBar, Toolbar, VideoList, StatusBar, SettingsPanel, SubtitlePicker


def _icon_path(name):
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


class SubHunterApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("SubHunter")
        self.geometry("950x680")
        self.minsize(750, 500)

        if sys.platform == "win32":
            ico = _icon_path("icon.ico")
            if os.path.exists(ico):
                self.iconbitmap(ico)
                self.after(200, lambda: self.iconbitmap(ico))
        else:
            png = _icon_path("icon.png")
            if os.path.exists(png):
                self._icon_img = PhotoImage(file=png)
                self.iconphoto(True, self._icon_img)

        # Load persistent config
        self.config = Config()

        self.is_dark = self.config.get("theme", "dark") == "dark"
        self.theme = DARK if self.is_dark else LIGHT
        self.is_downloading = False

        ctk.set_appearance_mode("dark" if self.is_dark else "light")
        self.configure(fg_color=self.theme.bg_deep)

        self._build()
        self._apply_config()
        self._check_updates()

    def _build(self):
        t = self.theme
        pad = 28

        # --- Header ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=pad, pady=(22, 0))

        brand = ctk.CTkFrame(header, fg_color="transparent")
        brand.pack(side="left")

        self._icon = ctk.CTkFrame(brand, width=38, height=38, fg_color=t.accent, corner_radius=8)
        self._icon.pack(side="left", padx=(0, 12))
        self._icon.pack_propagate(False)
        self._icon_lbl = ctk.CTkLabel(
            self._icon, text="SH",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color=t.bg_deep,
        )
        self._icon_lbl.place(relx=0.5, rely=0.5, anchor="center")

        titles = ctk.CTkFrame(brand, fg_color="transparent")
        titles.pack(side="left")
        self._title = ctk.CTkLabel(
            titles, text="SubHunter",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=t.text,
        )
        self._title.pack(anchor="w")
        self._subtitle = ctk.CTkLabel(
            titles, text="Subtitulos para peliculas y series, al instante.",
            font=ctk.CTkFont(family="Segoe UI", size=11), text_color=t.text_dim,
        )
        self._subtitle.pack(anchor="w")

        # Right header buttons
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right")

        self._ver = ctk.CTkLabel(
            right, text=f"v{VERSION}",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=t.accent_dim, fg_color=t.bg_input,
            corner_radius=4, width=36, height=18,
        )
        self._ver.pack(side="right", padx=(6, 0))

        self._theme_btn = ctk.CTkButton(
            right, text="Claro" if self.is_dark else "Oscuro",
            command=self._toggle_theme,
            width=55, height=22,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color=t.bg_input, hover_color=t.bg_card_hover,
            text_color=t.text_mid, corner_radius=4,
            border_width=1, border_color=t.border,
        )
        self._theme_btn.pack(side="right")

        self._settings_btn = ctk.CTkButton(
            right, text="Config", command=self._open_settings,
            width=55, height=22,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color=t.bg_input, hover_color=t.bg_card_hover,
            text_color=t.text_mid, corner_radius=4,
            border_width=1, border_color=t.border,
        )
        self._settings_btn.pack(side="right", padx=(0, 4))

        # Divider
        self._div = ctk.CTkFrame(self, height=1, fg_color=t.border)
        self._div.pack(fill="x", padx=pad, pady=(14, 0))

        # --- Toolbar ---
        self.toolbar = Toolbar(self, t)
        self.toolbar.pack(fill="x", padx=pad, pady=(12, 0))
        self.toolbar.on_folder(self._open_folder)
        self.toolbar.on_files(self._open_files)
        self.toolbar.on_download(self._start_download)

        # --- Video List ---
        self.video_list = VideoList(self, t)
        self.video_list.pack(fill="both", expand=True, padx=pad, pady=(8, 0))
        self.video_list.on_download_selected(self._start_download)
        self.video_list.on_find_alternative(self._find_alternative)
        self.video_list.on_list_changed(self._on_list_changed)

        # --- Progress ---
        self.progress = GlowBar(self, t, height=5)
        self.progress.pack(fill="x", padx=pad, pady=(8, 0))

        # --- Status Bar ---
        self.status_bar = StatusBar(self, t)
        self.status_bar.pack(fill="x", padx=pad, pady=(4, 12))

    # --- Config ---

    def _apply_config(self):
        """Apply loaded config to UI state."""
        lang = self.config.get("default_language", "Espanol")
        self.toolbar.lang_var.set(lang)
        self.toolbar.rename_var.set(self.config.get("auto_rename", True))

    def _open_settings(self):
        SettingsPanel(self, self.theme, self.config, on_save=self._on_settings_saved)

    def _on_settings_saved(self):
        self._apply_config()
        # Persist theme too
        self.config.set("theme", "dark" if self.is_dark else "light")
        self.config.save()
        self.status_bar.set_text("Configuracion guardada")

    # --- Actions ---

    def _open_folder(self):
        folder = filedialog.askdirectory(title="Seleccionar carpeta con videos")
        if folder:
            self.video_list.load_folder(folder)
            self._on_list_changed()
            self.progress.set(0)

    def _open_files(self):
        exts = " ".join(f"*{e}" for e in ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.ts', '.webm'))
        files = filedialog.askopenfilenames(
            title="Seleccionar archivos de video",
            filetypes=[("Videos", exts), ("Todos", "*.*")],
        )
        if files:
            self.video_list.load_files(list(files))
            self._on_list_changed()
            self.progress.set(0)

    def _on_list_changed(self):
        has = bool(self.video_list.rows)
        self.toolbar.set_has_items(has)
        count = len(self.video_list.rows)

        warning = getattr(self.video_list, '_dupe_warning', None)
        if warning:
            self.status_bar.set_text(f"{count} archivos  --  {warning}")
            self.video_list._dupe_warning = None
        else:
            self.status_bar.set_text(f"Listo  --  {count} archivos" if has else "Listo")

    def _build_downloader(self):
        active_langs = self.config.get("languages", ["Espanol"])
        toolbar_lang = self.toolbar.lang_var.get()
        if toolbar_lang not in active_langs:
            active_langs = [toolbar_lang] + active_langs
        lang_codes = [LANGUAGES[name] for name in active_langs if name in LANGUAGES]
        if not lang_codes:
            lang_codes = ["spa"]

        return SubtitleDownloader(
            lang_codes=lang_codes,
            auto_rename=self.toolbar.rename_var.get(),
            providers=self.config.get_active_providers() or None,
            provider_configs=self.config.get_provider_config(),
        )

    def _update_row_status(self, path, status, *args):
        row = self.video_list.get_row_by_path(path)
        if not row:
            return
        t = self.theme
        if status == "downloaded":
            provider = args[0] if args else "?"
            text, color = f"OK ({provider})", t.green
        elif status == "found":
            count = args[0] if args else 0
            text, color = f"{count} opciones", t.accent
        elif status == "alternative":
            provider = args[0] if args else "?"
            idx = args[1] if len(args) > 1 else "?"
            total = args[2] if len(args) > 2 else "?"
            text, color = f"Alt {idx}/{total} ({provider})", t.green
        elif status == "no_more":
            text, color = "Sin mas opciones", t.red
        else:
            status_map = {
                "searching":  ("Buscando...", t.amber),
                "not_found":  ("No encontrado", t.red),
                "error":      ("Error", t.red),
            }
            text, color = status_map.get(status, ("?", t.text_dim))
        self.after(0, lambda: row.set_status(text, color))

    def _start_download(self):
        if self.is_downloading:
            return

        paths = self.video_list.get_selected_paths()
        if not paths:
            messagebox.showinfo("SubHunter", "No hay videos seleccionados.")
            return

        self.is_downloading = True
        self.toolbar.set_downloading(True)
        self.status_bar.set_text("Buscando subtitulos disponibles...")

        dl = self._build_downloader()
        dl.on_item_status(self._update_row_status)

        def on_progress(p):
            self.after(0, lambda: self.progress.set(p))
            idx = int(p * len(paths))
            self.after(0, lambda: self.status_bar.set_text(
                f"Buscando {min(idx, len(paths))} de {len(paths)}..."
            ))

        def on_results(results):
            self.after(0, lambda: self._show_picker(results))

        dl.on_progress(on_progress)
        dl.search(paths, on_results=on_results)

    def _show_picker(self, results):
        self.is_downloading = False
        self.toolbar.set_downloading(False)

        total_found = sum(len(subs) for subs in results.values())
        if total_found == 0:
            self.status_bar.set_text("No se encontraron subtitulos")
            return

        self.status_bar.set_text(f"{total_found} subtitulos encontrados -- elige cuales descargar")

        SubtitlePicker(
            self, self.theme, results,
            on_confirm=self._download_picked
        )

    def _download_picked(self, selections, fallbacks=None):
        if not selections:
            self.status_bar.set_text("Ninguno seleccionado")
            return

        self.is_downloading = True
        self.toolbar.set_downloading(True)
        self.status_bar.set_text(f"Descargando {len(selections)} subtitulos...")

        dl = self._build_downloader()
        dl.on_item_status(self._update_row_status)

        def on_progress(p):
            self.after(0, lambda: self.progress.set(p))

        def on_complete(downloaded, failed):
            self.after(0, lambda: self._download_done(downloaded, failed))

        dl.on_progress(on_progress)
        dl.on_complete(on_complete)
        dl.download_selection(selections, fallbacks=fallbacks)

    def _download_done(self, downloaded, failed):
        self.is_downloading = False
        self.toolbar.set_downloading(False)
        self.video_list.update_stats()
        self.status_bar.set_text(
            f"Completado  --  {downloaded} descargados  /  {failed} no encontrados"
        )

    def _find_alternative(self, filepath, skip_index):
        """Search for an alternative subtitle for a specific file."""
        if self.is_downloading:
            return

        self.is_downloading = True
        self.toolbar.set_downloading(True)

        dl = self._build_downloader()
        dl.on_item_status(self._update_row_status)

        def on_complete(downloaded, failed):
            self.after(0, lambda: self._download_done(downloaded, failed))

        def on_progress(p):
            self.after(0, lambda: self.progress.set(p))

        dl.on_progress(on_progress)
        dl.on_complete(on_complete)
        dl.download_alternative(filepath, skip_index)

    # --- Theme ---

    def _toggle_theme(self):
        self.is_dark = not self.is_dark
        self.theme = DARK if self.is_dark else LIGHT
        ctk.set_appearance_mode("dark" if self.is_dark else "light")
        self._theme_btn.configure(text="Claro" if self.is_dark else "Oscuro")
        self.config.set("theme", "dark" if self.is_dark else "light")
        self.config.save()
        self._apply_theme()

    # --- Updates ---

    def _check_updates(self):
        updater = Updater()
        updater.on_update_available(
            lambda ver, url: self.after(0, lambda: self._show_update_banner(ver, url))
        )
        updater.check()

    def _show_update_banner(self, version, download_url):
        t = self.theme
        self._update_bar = ctk.CTkFrame(
            self, height=32, fg_color=t.accent_dim, corner_radius=0
        )
        self._update_bar.pack(fill="x", side="bottom")
        self._update_bar.pack_propagate(False)

        ctk.CTkLabel(
            self._update_bar,
            text=f"Nueva version v{version} disponible",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=t.bg_deep,
        ).pack(side="left", padx=(16, 8))

        ctk.CTkButton(
            self._update_bar, text="Descargar",
            command=lambda: Updater.open_download(download_url),
            width=80, height=22,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=t.bg_deep, hover_color=t.bg_card,
            text_color=t.accent, corner_radius=4,
        ).pack(side="left")

        ctk.CTkButton(
            self._update_bar, text="X",
            command=self._update_bar.destroy,
            width=24, height=22,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="transparent", hover_color=t.accent,
            text_color=t.bg_deep, corner_radius=4,
        ).pack(side="right", padx=8)

    def _apply_theme(self):
        t = self.theme
        self.configure(fg_color=t.bg_deep)
        self._icon.configure(fg_color=t.accent)
        self._icon_lbl.configure(text_color=t.bg_deep)
        self._title.configure(text_color=t.text)
        self._subtitle.configure(text_color=t.text_dim)
        self._ver.configure(text_color=t.accent_dim, fg_color=t.bg_input)
        self._theme_btn.configure(
            fg_color=t.bg_input, hover_color=t.bg_card_hover,
            text_color=t.text_mid, border_color=t.border,
        )
        self._settings_btn.configure(
            fg_color=t.bg_input, hover_color=t.bg_card_hover,
            text_color=t.text_mid, border_color=t.border,
        )
        self._div.configure(fg_color=t.border)
        self.toolbar.apply_theme(t)
        self.video_list.apply_theme(t)
        self.progress.apply_theme(t)
        self.status_bar.apply_theme(t)


def main():
    app = SubHunterApp()
    app.mainloop()
