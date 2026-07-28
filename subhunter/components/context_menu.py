import tkinter as tk
from subhunter.core.theme import Theme, FONT_UI, FONT_MONO


class ContextMenu:
    """Right-click context menu for the video list."""

    def __init__(self, parent, theme: Theme):
        self.parent = parent
        self.theme = theme
        self._actions = {}
        self._menu = None

    def add_action(self, label: str, callback):
        self._actions[label] = callback

    def show(self, event):
        if self._menu:
            self._menu.destroy()

        t = self.theme
        self._menu = tk.Menu(
            self.parent, tearoff=0,
            bg=t.bg_card, fg=t.text,
            activebackground=t.accent_dim, activeforeground=t.bg_deep,
            relief="flat", bd=1,
            font=(FONT_UI, 10),
        )

        for label, cb in self._actions.items():
            if label == "---":
                self._menu.add_separator()
            else:
                self._menu.add_command(label=label, command=cb)

        try:
            self._menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu.grab_release()

    def apply_theme(self, t: Theme):
        self.theme = t
