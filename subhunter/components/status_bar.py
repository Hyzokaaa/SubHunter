import customtkinter as ctk
from subhunter.core.theme import Theme, FONT_UI, FONT_MONO


class StatusBar(ctk.CTkFrame):
    """Footer with status text and provider info."""

    def __init__(self, parent, theme: Theme, **kwargs):
        super().__init__(parent, fg_color="transparent", height=30, **kwargs)
        self.theme = theme

        self._status = ctk.CTkLabel(
            self, text="Listo",
            font=ctk.CTkFont(family=FONT_UI, size=11),
            text_color=theme.text_dim, anchor="w",
        )
        self._status.pack(side="left")

        self._providers = ctk.CTkLabel(
            self, text="OpenSubtitles  |  Addic7ed  |  Podnapisi",
            font=ctk.CTkFont(family=FONT_MONO, size=9),
            text_color=theme.provider, anchor="e",
        )
        self._providers.pack(side="right")

    def set_text(self, text: str):
        self._status.configure(text=text)

    def apply_theme(self, t: Theme):
        self.theme = t
        self._status.configure(text_color=t.text_dim)
        self._providers.configure(text_color=t.provider)
