"""Fill in IMDb/TVDB ids from the title, as Sonarr/Radarr would do for Bazarr.

Several providers (YIFY, OpenSubtitles by id, Gestdown...) search by id only.
Cinemeta (Stremio's public metadata API) needs no key.
"""
import logging
import os
import re
from functools import lru_cache
from urllib.parse import quote

import requests
from guessit import guessit

from subliminal.video import Episode, Movie

logger = logging.getLogger(__name__)

CINEMETA_URL = "https://v3-cinemeta.strem.io"
TIMEOUT = 10


def _norm(text):
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


@lru_cache(maxsize=256)
def _search(kind, title):
    r = requests.get(f"{CINEMETA_URL}/catalog/{kind}/top/search={quote(title)}.json",
                     timeout=TIMEOUT)
    r.raise_for_status()
    return tuple(r.json().get("metas") or [])


@lru_cache(maxsize=256)
def _series_tvdb_id(imdb_id):
    r = requests.get(f"{CINEMETA_URL}/meta/series/{imdb_id}.json", timeout=TIMEOUT)
    r.raise_for_status()
    tvdb = (r.json().get("meta") or {}).get("tvdb_id")
    return int(tvdb) if tvdb else None


def _pick(metas, title, year):
    wanted = _norm(title)
    exact = [m for m in metas if _norm(m.get("name")) == wanted]
    if year:
        dated = [m for m in exact if str(m.get("releaseInfo") or "").startswith(str(year))]
        if dated:
            return dated[0]
    return exact[0] if exact else None


def refine_ids(video):
    try:
        if isinstance(video, Movie) and not video.imdb_id and video.title:
            meta = _pick(_search("movie", video.title), video.title, video.year)
            if meta:
                video.imdb_id = meta.get("imdb_id") or meta.get("id")
        elif isinstance(video, Episode) and video.series and not video.series_imdb_id:
            meta = _pick(_search("series", video.series), video.series, video.year)
            if meta:
                video.series_imdb_id = meta.get("imdb_id") or meta.get("id")
                if not video.series_tvdb_id:
                    video.series_tvdb_id = _series_tvdb_id(video.series_imdb_id)
        else:
            return
        logger.info("Ids for %r: imdb=%s series_imdb=%s series_tvdb=%s", video,
                    getattr(video, "imdb_id", None), getattr(video, "series_imdb_id", None),
                    getattr(video, "series_tvdb_id", None))
    except Exception as e:
        logger.warning("Could not look up ids for %r: %s", video, e)


def fix_country_title(video):
    """guessit reads "The.Last.of.Us" as title "The Last of" + country US.

    A country written in capitals ("Shameless.US") is a real country tag; any
    other casing is part of the title.
    """
    name = os.path.basename(video.name)
    guess = guessit(name)
    country = guess.get("country")
    title = guess.get("title")
    if not country or not title:
        return
    tokens = re.split(r"[._\s\-]+", name)
    title_len = len(re.split(r"[._\s\-]+", title))
    for i in range(len(tokens) - title_len):
        if _norm("".join(tokens[i:i + title_len])) != _norm(title):
            continue
        nxt = tokens[i + title_len]
        if nxt.lower() == str(country.alpha2).lower() and not nxt.isupper():
            fixed = f"{title} {nxt}"
            if isinstance(video, Episode):
                video.series = fixed
            elif isinstance(video, Movie):
                video.title = fixed
            logger.debug("Title fixed: %r -> %r", title, fixed)
        return
