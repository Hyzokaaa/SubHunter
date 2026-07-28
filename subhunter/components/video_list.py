import os
import customtkinter as ctk
from subhunter.core.theme import Theme, FONT_UI, FONT_MONO
from subhunter.core.constants import VIDEO_EXTENSIONS
from .video_row import VideoRow
from .context_menu import ContextMenu


class VideoList(ctk.CTkFrame):
    """Scrollable list of video rows with stats bar, empty state, and context menu."""

    def __init__(self, parent, theme: Theme, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.theme = theme
        self.rows: list[VideoRow] = []

        self._on_download_selected = None
        self._on_find_alternative = None
        self._on_list_changed = None
        self._alt_indices = {}  # track alternative index per filepath

        self._build(theme)
        self._build_context_menu(theme)

    def on_download_selected(self, cb):
        self._on_download_selected = cb

    def on_find_alternative(self, cb):
        self._on_find_alternative = cb

    def on_list_changed(self, cb):
        self._on_list_changed = cb

    def _build(self, t: Theme):
        # Stats bar
        self._stats_frame = ctk.CTkFrame(self, fg_color="transparent", height=26)
        self._stats_frame.pack(fill="x", pady=(0, 4))

        self._stats = ctk.CTkLabel(
            self._stats_frame, text="",
            font=ctk.CTkFont(family=FONT_UI, size=11),
            text_color=t.text_dim, anchor="w",
        )
        self._stats.pack(side="left")

        btn_cfg = dict(
            height=20, font=ctk.CTkFont(family=FONT_UI, size=10),
            fg_color=t.bg_input, hover_color=t.bg_card_hover,
            text_color=t.text_mid, corner_radius=4,
            border_width=1, border_color=t.border,
        )

        self._all_btn = ctk.CTkButton(
            self._stats_frame, text="Todos", width=50,
            command=self._select_all, **btn_cfg,
        )
        self._none_btn = ctk.CTkButton(
            self._stats_frame, text="Ninguno", width=60,
            command=self._select_none, **btn_cfg,
        )

        # Path bar
        self._path_frame = ctk.CTkFrame(
            self, fg_color=t.bg_surface, corner_radius=4,
            height=28, border_width=1, border_color=t.border,
        )
        self._path_frame.pack(fill="x", pady=(0, 6))

        self._clear_btn = ctk.CTkButton(
            self._path_frame, text="X", width=24, height=20,
            font=ctk.CTkFont(family=FONT_MONO, size=11, weight="bold"),
            fg_color="transparent", hover_color=t.red,
            text_color=t.text_dim, corner_radius=4,
            command=self.clear,
        )

        self._path = ctk.CTkLabel(
            self._path_frame,
            text="  Selecciona una carpeta o archivos de video...",
            font=ctk.CTkFont(family=FONT_MONO, size=11),
            text_color=t.text_dim, anchor="w",
        )
        self._path.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=4)

        # Scrollable area
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=t.bg_surface, corner_radius=6,
            border_width=1, border_color=t.border,
            scrollbar_button_color=t.accent_dim,
            scrollbar_button_hover_color=t.accent,
        )
        self._scroll.pack(fill="both", expand=True)

        # Right-click binding on scrollable area
        self._scroll.bind("<Button-3>", self._on_right_click)

        self._show_empty(t)

    def _build_context_menu(self, t: Theme):
        self._ctx = ContextMenu(self, t)
        self._ctx.add_action("Descargar seleccionados", self._ctx_download)
        self._ctx.add_action("Buscar alternativa (seleccionados)", self._ctx_alternative)
        self._ctx.add_action("---", None)
        self._ctx.add_action("Seleccionar todos", self._select_all)
        self._ctx.add_action("Deseleccionar todos", self._select_none)
        self._ctx.add_action("Invertir seleccion", self._invert_selection)
        self._ctx.add_action("---", None)
        self._ctx.add_action("Quitar seleccionados", self._remove_selected)
        self._ctx.add_action("Limpiar lista", self.clear)

    def _on_right_click(self, event):
        if self.rows:
            self._ctx.show(event)

    def _ctx_download(self):
        if self._on_download_selected:
            self._on_download_selected()

    def _ctx_alternative(self):
        if self._on_find_alternative:
            selected = [r.filepath for r in self.rows if r.check_var.get()]
            for fp in selected:
                # Increment the alternative index for each file
                idx = self._alt_indices.get(fp, 0) + 1
                self._alt_indices[fp] = idx
                self._on_find_alternative(fp, idx)

    def reset_alt_index(self, filepath):
        self._alt_indices.pop(filepath, None)

    def _invert_selection(self):
        for r in self.rows:
            r.check_var.set(not r.check_var.get())

    def _remove_selected(self):
        to_keep = []
        for r in self.rows:
            if r.check_var.get():
                r.destroy()
            else:
                to_keep.append(r)
        self.rows = to_keep
        self._refresh_stats()
        self._notify_changed()

        if not self.rows:
            self._show_empty(self.theme)

    def _notify_changed(self):
        if self._on_list_changed:
            self._on_list_changed()

    def _show_empty(self, t: Theme):
        self._empty = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._empty.pack(fill="both", expand=True, pady=50)

        ctk.CTkLabel(
            self._empty, text="CC",
            font=ctk.CTkFont(family=FONT_MONO, size=36, weight="bold"),
            text_color=t.accent_dim,
        ).pack()
        ctk.CTkLabel(
            self._empty, text="Usa los botones para cargar videos",
            font=ctk.CTkFont(family=FONT_UI, size=12),
            text_color=t.text_dim,
        ).pack(pady=(8, 0))
        ctk.CTkLabel(
            self._empty,
            text="Click derecho para mas opciones",
            font=ctk.CTkFont(family=FONT_UI, size=10),
            text_color=t.border,
        ).pack(pady=(2, 0))

    def load_folder(self, folder: str):
        files = []
        for f in sorted(os.listdir(folder)):
            if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS:
                files.append(os.path.join(folder, f))
        self._add_files(files, folder)

    def load_files(self, paths: list[str]):
        if paths:
            self._add_files(paths, os.path.dirname(paths[0]))

    def _add_files(self, paths: list[str], display_path: str):
        if hasattr(self, "_empty") and self._empty.winfo_exists():
            self._empty.destroy()

        # Normalize existing paths for duplicate detection
        existing = {os.path.normpath(r.filepath) for r in self.rows}
        dupes = []

        t = self.theme
        added = 0
        for fp in paths:
            norm = os.path.normpath(fp)
            if norm in existing:
                dupes.append(os.path.basename(fp))
                continue

            existing.add(norm)
            has_sub = os.path.exists(os.path.splitext(fp)[0] + ".srt")
            row = VideoRow(self._scroll, fp, t, has_sub=has_sub)
            row.pack(fill="x", padx=3, pady=1)
            row.bind("<Button-3>", self._on_right_click)
            for child in row.winfo_children():
                child.bind("<Button-3>", self._on_right_click)
            self.rows.append(row)
            added += 1

        # Update path display
        if self.rows:
            short = display_path if len(display_path) <= 85 else "..." + display_path[-82:]
            self._path.configure(text=f"  {short}")
            self._all_btn.pack(side="right", padx=(3, 0))
            self._none_btn.pack(side="right", padx=(3, 0))
            self._clear_btn.pack(side="right", padx=(0, 6), pady=3)

        self._refresh_stats()

        # Warn about duplicates
        if dupes:
            n = len(dupes)
            preview = ", ".join(dupes[:3])
            if n > 3:
                preview += f" y {n - 3} mas"
            self._on_duplicates_found(n, preview)

        return added

    def _on_duplicates_found(self, count: int, preview: str):
        """Notify parent about duplicates via status bar."""
        if self._on_list_changed:
            self._dupe_warning = f"{count} duplicado{'s' if count > 1 else ''} ignorado{'s' if count > 1 else ''}: {preview}"
        else:
            self._dupe_warning = None

    def clear(self):
        for r in self.rows:
            r.destroy()
        self.rows.clear()
        self._stats.configure(text="")
        self._all_btn.pack_forget()
        self._none_btn.pack_forget()
        self._clear_btn.pack_forget()
        self._path.configure(text="  Selecciona una carpeta o archivos de video...")
        self._show_empty(self.theme)
        self._notify_changed()

    def get_selected_paths(self) -> list[str]:
        return [r.filepath for r in self.rows if r.check_var.get()]

    def get_row_by_path(self, path: str):
        for r in self.rows:
            if r.filepath == path:
                return r
        return None

    def update_stats(self):
        self._refresh_stats()

    def _refresh_stats(self):
        sub_count = sum(
            1 for r in self.rows
            if os.path.exists(os.path.splitext(r.filepath)[0] + ".srt")
        )
        total = len(self.rows)
        self._stats.configure(
            text=f"{total} videos   {sub_count} con sub   {total - sub_count} pendientes"
        )

    def _select_all(self):
        for r in self.rows:
            r.check_var.set(True)

    def _select_none(self):
        for r in self.rows:
            r.check_var.set(False)

    def apply_theme(self, t: Theme):
        self.theme = t
        self._ctx.apply_theme(t)
        self._stats.configure(text_color=t.text_dim)
        for btn in (self._all_btn, self._none_btn):
            btn.configure(
                fg_color=t.bg_input, hover_color=t.bg_card_hover,
                text_color=t.text_mid, border_color=t.border,
            )
        self._path_frame.configure(fg_color=t.bg_surface, border_color=t.border)
        self._path.configure(text_color=t.text_dim)
        self._clear_btn.configure(hover_color=t.red, text_color=t.text_dim)
        self._scroll.configure(
            fg_color=t.bg_surface, border_color=t.border,
            scrollbar_button_color=t.accent_dim,
            scrollbar_button_hover_color=t.accent,
        )
        for r in self.rows:
            r.apply_theme(t)
