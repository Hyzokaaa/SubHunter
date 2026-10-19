"""SubHunter's own providers and the catalog shown in Settings.

Most providers come from Bazarr's subliminal_patch (vendored). This module adds:
- opensubtitles: OpenSubtitles.org XML-RPC, ported from subliminal 2.7 (MIT)
- opensubtitlescom: Bazarr's provider, but usable without an account
- animetosho_net: see anime.py
"""
import base64
import logging
import os
import re
import zlib
from xmlrpc.client import ServerProxy

from babelfish import language_converters
from guessit import guessit
from subzero.language import Language

from subliminal.exceptions import (
    AuthenticationError, ConfigurationError, DownloadLimitExceeded, ProviderError,
    ServiceUnavailable,
)
from subliminal.providers import TimeoutSafeTransport
from subliminal.video import Episode, Movie
from subliminal_patch.extensions import provider_registry
from subliminal_patch.providers import Provider
from subliminal_patch.providers.opensubtitlescom import OpenSubtitlesComProvider
from subliminal_patch.subtitle import Subtitle, guess_matches

from .anime import AnimeToshoNetProvider
from .constants import DEFAULT_PROVIDERS

logger = logging.getLogger(__name__)

# Public key subliminal ships for OpenSubtitles.com anonymous access
OPENSUBTITLESCOM_API_KEY = "mij33pjc3kOlup1qOKxnWWxvle2kFbMH"
OPENSUBTITLESCOM_HOST = "api.opensubtitles.com"


class OpenSubtitlesOrgSubtitle(Subtitle):
    provider_name = "opensubtitles"
    hash_verifiable = True
    series_re = re.compile(r'^"(?P<series_name>.*)" (?P<series_title>.*)$')

    def __init__(self, language, subtitle_id, hearing_impaired, page_link, matched_by,
                 movie_kind, moviehash, movie_name, movie_release_name, movie_year,
                 movie_imdb_id, series_season, series_episode, filename, encoding):
        super().__init__(language, hearing_impaired=hearing_impaired,
                         page_link=page_link, encoding=encoding)
        self.subtitle_id = subtitle_id
        self.matched_by = matched_by
        self.movie_kind = movie_kind
        self.moviehash = moviehash
        self.movie_name = movie_name
        self.movie_release_name = movie_release_name
        self.movie_year = movie_year
        self.movie_imdb_id = movie_imdb_id
        self.series_season = series_season
        self.series_episode = series_episode
        self.filename = filename
        self.release_info = movie_release_name or filename

    @property
    def id(self):
        return str(self.subtitle_id)

    def _series_part(self, group):
        m = self.series_re.match(self.movie_name or "")
        return m.group(group) if m else ""

    def get_matches(self, video):
        if (isinstance(video, Episode) and self.movie_kind != "episode") or \
                (isinstance(video, Movie) and self.movie_kind != "movie"):
            return set()

        is_episode = self.movie_kind == "episode"
        matches = guess_matches(video, {
            "title": self._series_part("series_name") if is_episode else self.movie_name,
            "episode_title": self._series_part("series_title") if is_episode else None,
            "year": self.movie_year,
            "season": self.series_season,
            "episode": self.series_episode,
        })

        if self.matched_by == "tag" and (not video.imdb_id or self.movie_imdb_id == video.imdb_id):
            matches |= {"series", "year", "season", "episode"} if is_episode else {"title", "year"}

        for name in (self.movie_release_name, self.filename):
            if name:
                matches |= guess_matches(video, guessit(name, {"type": self.movie_kind}))

        if self.moviehash and video.hashes.get("opensubtitles") == self.moviehash:
            needed = {"series", "season", "episode"} if is_episode else {"title"}
            if needed <= matches:
                matches.add("hash")

        if video.imdb_id and self.movie_imdb_id == video.imdb_id:
            matches.add("imdb_id")
        return matches


class OpenSubtitlesOrgProvider(Provider):
    """OpenSubtitles.org (XML-RPC), anonymous or with an account."""

    languages = {Language.fromopensubtitles(code)
                 for code in language_converters["szopensubtitles"].codes}
    video_types = (Episode, Movie)
    subtitle_class = OpenSubtitlesOrgSubtitle
    server_url = "https://api.opensubtitles.org/xml-rpc"
    user_agent = "VLSub 0.11.1"

    def __init__(self, username=None, password=None, timeout=10):
        if any((username, password)) and not all((username, password)):
            raise ConfigurationError("Username and password must be specified")
        self.server = ServerProxy(self.server_url, TimeoutSafeTransport(timeout))
        self.username = username or ""
        self.password = password or ""
        self.token = None

    def initialize(self):
        response = _checked(self.server.LogIn(self.username, self.password, "eng", self.user_agent))
        self.token = str(response["token"])

    def terminate(self):
        try:
            _checked(self.server.LogOut(self.token))
        except Exception:
            pass
        self.token = None

    def query(self, languages, moviehash=None, size=None, imdb_id=None, query=None,
              season=None, episode=None, tag=None):
        criteria = []
        if moviehash and size:
            criteria.append({"moviehash": moviehash, "moviebytesize": str(size)})
        if imdb_id:
            imdb = imdb_id[2:] if imdb_id.startswith("tt") else imdb_id
            if season and episode:
                criteria.append({"imdbid": imdb, "season": season, "episode": episode})
            else:
                criteria.append({"imdbid": imdb})
        if tag:
            criteria.append({"tag": tag})
        if query and season is not None and episode is not None:
            criteria.append({"query": query.replace("'", ""), "season": season, "episode": episode})
        elif query:
            criteria.append({"query": query.replace("'", "")})
        if not criteria:
            raise ValueError("Not enough information")

        sublanguageid = ",".join(sorted({l.szopensubtitles for l in languages}))
        for criterion in criteria:
            criterion["sublanguageid"] = sublanguageid

        response = _checked(self.server.SearchSubtitles(self.token, criteria))
        subtitles = []
        for item in response.get("data") or []:
            try:
                language = Language.fromszopensubtitles(item["SubLanguageID"])
            except Exception:
                continue
            hi = bool(int(item["SubHearingImpaired"]))
            if hi:
                language = Language.rebuild(language, hi=True)
            imdb = item.get("IDMovieImdb")
            subtitles.append(self.subtitle_class(
                language=language,
                subtitle_id=str(int(item["IDSubtitleFile"])),
                hearing_impaired=hi,
                page_link=item["SubtitlesLink"],
                matched_by=item["MatchedBy"],
                movie_kind=item["MovieKind"],
                moviehash=item["MovieHash"],
                movie_name=item["MovieName"],
                movie_release_name=item["MovieReleaseName"],
                movie_year=int(item["MovieYear"]) if item["MovieYear"] else None,
                movie_imdb_id=f"tt{int(imdb):07d}" if imdb else None,
                series_season=int(item["SeriesSeason"]) if item["SeriesSeason"] else None,
                series_episode=int(item["SeriesEpisode"]) if item["SeriesEpisode"] else None,
                filename=item["SubFileName"],
                encoding=item.get("SubEncoding") or None,
            ))
        return subtitles

    def list_subtitles(self, video, languages):
        season = episode = None
        if isinstance(video, Episode):
            query, season, episode = video.series, video.season, video.episode
        else:
            query = video.title
        return self.query(
            languages,
            moviehash=video.hashes.get("opensubtitles"),
            size=video.size,
            imdb_id=video.imdb_id,
            query=query,
            season=season,
            episode=episode,
            tag=os.path.basename(video.name),
        )

    def download_subtitle(self, subtitle):
        response = _checked(self.server.DownloadSubtitles(self.token, [subtitle.subtitle_id]))
        subtitle.content = zlib.decompress(base64.b64decode(response["data"][0]["data"]), 47)


def _checked(response):
    status_code = int(response["status"][:3])
    if status_code in (401, 406, 414, 415):
        raise AuthenticationError(response["status"])
    if status_code == 407:
        raise DownloadLimitExceeded(response["status"])
    if status_code == 503:
        raise ServiceUnavailable(response["status"])
    if status_code != 200:
        raise ProviderError(response["status"])
    return response


class OpenSubtitlesComAnonProvider(OpenSubtitlesComProvider):
    """Bazarr's OpenSubtitles.com provider, also usable without an account."""

    def __init__(self, username=None, password=None, api_key=None, **kwargs):
        self._anonymous = not (username and password)
        super().__init__(
            username=username or "anonymous", password=password or "anonymous",
            api_key=api_key or OPENSUBTITLESCOM_API_KEY, **kwargs,
        )
        self.session.headers["User-Agent"] = "SubHunter v1"

    def initialize(self):
        if not self._anonymous:
            return super().initialize()
        self._started = __import__("time").time()
        self.server_hostname = OPENSUBTITLESCOM_HOST
        self.token = None

    def search_titles(self, title):
        # Bazarr gets exact titles from Sonarr/Radarr; ours come from file names,
        # so compare ignoring punctuation ("Show: Subtitle" vs "Show Subtitle").
        title_id = super().search_titles(title)
        if title_id:
            return title_id
        r = self.session.get(self.server_url() + "features",
                             params={"query": title.lower()}, timeout=30)
        if not r.ok:
            return None
        wanted = _alnum(title)
        kind = "tvshow" if isinstance(self.video, Episode) else "movie"
        for result in r.json().get("data") or []:
            attrs = result.get("attributes") or {}
            if attrs.get("feature_type", "").lower().replace(" ", "") not in (kind, ""):
                continue
            if _alnum(attrs.get("title") or "") == wanted and \
                    (not self.video.year or str(self.video.year) == str(attrs.get("year"))):
                return self.sanitize_external_ids(result["id"])
        return None

    def download_subtitle(self, subtitle):
        if not self._anonymous:
            return super().download_subtitle(subtitle)
        r = self.session.post(self.server_url() + "download",
                              json={"file_id": subtitle.file_id, "sub_format": "srt"},
                              headers={"Accept": "application/json"},
                              timeout=30)
        if r.status_code == 406:
            raise DownloadLimitExceeded("OpenSubtitles.com anonymous download limit reached")
        r.raise_for_status()
        link = r.json().get("link")
        if not link:
            raise ProviderError("OpenSubtitles.com returned no download link")
        content = self.session.get(link, timeout=30)
        content.raise_for_status()
        subtitle.content = content.content


def _alnum(text):
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def register_custom_providers():
    provider_registry.register("opensubtitles", OpenSubtitlesOrgProvider)
    provider_registry.register("opensubtitlescom", OpenSubtitlesComAnonProvider)
    provider_registry.register("animetosho_net", AnimeToshoNetProvider)


# ---------------------------------------------------------------------------
# Catalog for the settings window
# ---------------------------------------------------------------------------

# Replaced by animetosho_net (they need AniDB API credentials / dead domain)
HIDDEN_PROVIDERS = {"animetosho", "animetosho_xyz"}


PROVIDER_INFO = {
    # name: (label, description)
    "opensubtitlescom": ("OpenSubtitles.com", "Todos los idiomas. Sin cuenta: pocas descargas al dia"),
    "opensubtitles": ("OpenSubtitles.org", "Todos los idiomas (API clasica)"),
    "animetosho_net": ("AnimeTosho", "Anime: pistas extraidas de releases (Crunchyroll, etc.)"),
    "tsukihime": ("TsukiHime", "Anime: espejo de AnimeTosho"),
    "subtitulamostv": ("Subtitulamos.tv", "Series en espanol"),
    "subx": ("SubX", "Espanol latino (reemplazo de Subdivx)"),
    "subdl": ("SubDL", "Muchos idiomas"),
    "subsource": ("SubSource", "Muchos idiomas"),
    "addic7ed": ("Addic7ed", "Series, muchos idiomas"),
    "gestdown": ("Gestdown", "Series (espejo de Addic7ed)"),
    "yifysubtitles": ("YIFY Subtitles", "Peliculas"),
    "subtis": ("Subtis", "Peliculas en espanol"),
    "subtitlecat": ("SubtitleCat", "Muchos idiomas, incluye traducciones automaticas"),
    "embeddedsubtitles": ("Subtitulos incrustados", "Extrae pistas del propio video (requiere ffmpeg)"),
    "bsplayer": ("BSPlayer", "Muchos idiomas"),
    "tvsubtitles": ("TVSubtitles", "Series"),
    "jimaku": ("Jimaku", "Anime en japones"),
    "whisperai": ("Whisper AI", "Genera subtitulos con IA (servidor propio)"),
    "subsarr": ("Subsarr", "Servidor propio"),
    "subsdump": ("SubsDump", "Servidor propio"),
    "avistaz": ("AvistaZ", "Tracker privado"),
    "cinemaz": ("CinemaZ", "Tracker privado"),
    "hdbits": ("HDBits", "Tracker privado"),
    "karagarga": ("Karagarga", "Tracker privado"),
}

# Constructor arguments the user may need to fill in, with their label
CREDENTIAL_FIELDS = {
    "username": "Usuario",
    "password": "Contrasena",
    "email": "Email",
    "hashed_password": "Contrasena (hash)",
    "api_key": "API key",
    "token": "Token",
    "passkey": "Passkey",
    "cookies": "Cookies",
    "base_url": "URL del servidor",
    "endpoint": "URL del servidor",
}
SECRET_FIELDS = {"password", "hashed_password", "api_key", "token", "passkey", "cookies"}

# Required non-credential options
DEFAULT_OPTIONS = {
    "jimaku": {"enable_name_search_fallback": True, "enable_archives_download": False,
               "enable_ai_subs": False},
    "subf2m": {"user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"},
}

_catalog = None


def provider_catalog():
    """List of dicts describing every usable provider (cached)."""
    global _catalog
    if _catalog is not None:
        return _catalog

    import inspect
    register_custom_providers()
    catalog = []
    for name in provider_registry.names():
        if name in HIDDEN_PROVIDERS:
            continue
        try:
            cls = provider_registry[name]
            params = list(inspect.signature(cls.__init__).parameters)[1:]
        except Exception:
            continue
        fields = [p for p in params if p in CREDENTIAL_FIELDS]
        if name == "opensubtitlescom":
            fields.remove("api_key")  # SubHunter supplies one
        # Providers that refuse to start without configuration
        try:
            cls(**DEFAULT_OPTIONS.get(name, {}))
            needs_config = False
        except Exception:
            needs_config = True
        languages = {getattr(l, "alpha3", None) for l in (getattr(cls, "languages", None) or [])}
        label, desc = PROVIDER_INFO.get(name, (name.replace("_", " ").title(), ""))
        catalog.append({
            "name": name,
            "label": label,
            "description": desc,
            "fields": fields,
            "needs_config": needs_config,
            "languages": languages - {None},
            "default": name in DEFAULT_PROVIDERS,
        })
    catalog.sort(key=lambda p: (not p["default"], p["needs_config"], p["label"].lower()))
    _catalog = catalog
    return catalog
