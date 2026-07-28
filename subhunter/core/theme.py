import sys
from dataclasses import dataclass

if sys.platform == "win32":
    FONT_UI = "Segoe UI"
    FONT_MONO = "Consolas"
elif sys.platform == "darwin":
    FONT_UI = "SF Pro"
    FONT_MONO = "SF Mono"
else:
    FONT_UI = "sans-serif"
    FONT_MONO = "monospace"


@dataclass
class Theme:
    bg_deep: str
    bg_card: str
    bg_card_hover: str
    bg_surface: str
    bg_input: str
    accent: str
    accent_dim: str
    accent_bright: str
    text: str
    text_dim: str
    text_mid: str
    green: str
    red: str
    amber: str
    border: str
    badge_bg: str
    track: str
    provider: str


DARK = Theme(
    bg_deep="#0a0a0f",
    bg_card="#12121a",
    bg_card_hover="#1a1a25",
    bg_surface="#0e0e16",
    bg_input="#16161f",
    accent="#d4a54a",
    accent_dim="#8a6d2e",
    accent_bright="#f0c960",
    text="#e8e4dc",
    text_dim="#6b6760",
    text_mid="#9a958c",
    green="#4a9e6a",
    red="#c44d4d",
    amber="#d4a017",
    border="#2a2a35",
    badge_bg="#1e1e28",
    track="#1a1a22",
    provider="#2a2a35",
)

LIGHT = Theme(
    bg_deep="#f5f2ed",
    bg_card="#ffffff",
    bg_card_hover="#f0ece5",
    bg_surface="#faf8f4",
    bg_input="#eeeae3",
    accent="#b8860b",
    accent_dim="#c9a43e",
    accent_bright="#daa520",
    text="#1a1714",
    text_dim="#8a8580",
    text_mid="#6b665f",
    green="#2e8b57",
    red="#c0392b",
    amber="#d4a017",
    border="#d6d0c6",
    badge_bg="#efe9df",
    track="#e8e2d8",
    provider="#c8c2b8",
)
