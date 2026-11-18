import os

VIDEO_EXTENSIONS = {
    '.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv',
    '.webm', '.m4v', '.mpg', '.mpeg', '.ts',
}

SUBTITLE_FILE_EXTENSIONS = ('.srt', '.ass', '.ssa', '.vtt')


def find_subtitles(video_path):
    """Subtitle files next to a video: 'name.srt' or with a language tag ('name.es.ass')."""
    folder = os.path.dirname(video_path) or "."
    base = os.path.splitext(os.path.basename(video_path))[0]
    found = []
    try:
        names = os.listdir(folder)
    except OSError:
        return found
    for f in names:
        stem, ext = os.path.splitext(f)
        if ext.lower() not in SUBTITLE_FILE_EXTENSIONS:
            continue
        # The middle part may be a short language tag only, so 'Show.S01E01'
        # does not claim 'Show.S01E01.Extended.srt'
        if stem == base or (stem.startswith(base + ".") and len(stem) - len(base) <= 7):
            found.append(os.path.join(folder, f))
    return sorted(found)

LANGUAGES = {
    "Espanol": "spa",
    "English": "eng",
    "Portugues": "por",
    "Francais": "fra",
    "Italiano": "ita",
    "Deutsch": "deu",
    "Chinese": "zho",
    "Japanese": "jpn",
    "Korean": "kor",
    "Arabic": "ara",
    "Russian": "rus",
}

# Enabled on first run; the full list comes from providers.provider_catalog()
DEFAULT_PROVIDERS = {
    "opensubtitlescom", "opensubtitles", "animetosho_net", "subtitulamostv",
    "gestdown", "yifysubtitles", "subtis",
}
