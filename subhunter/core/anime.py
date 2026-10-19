"""Anime support: maps a series title + TVDB season/episode to AniDB ids and
provides an AnimeTosho.net subtitle provider that needs no API keys.

Data sources (cached under ~/.subhunter/cache):
- AniDB titles dump: title (any language/synonym) -> AniDB anime id
- Anime-Lists: AniDB anime id <-> TVDB series/season/episode offset
"""
import gzip
import json
import logging
import lzma
import os
import re
import threading
import time
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

import requests
from guessit import guessit
from subzero.language import Language

from subliminal.video import Episode
from subliminal_patch.providers import Provider
from subliminal_patch.subtitle import Subtitle, guess_matches

from .config import CONFIG_DIR

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(CONFIG_DIR, "cache")
USER_AGENT = "SubHunter"

ANIDB_TITLES_URL = "https://anidb.net/api/anime-titles.xml.gz"
ANIME_LIST_URL = "https://raw.githubusercontent.com/Anime-Lists/anime-lists/master/anime-list-master.xml"
# AniDB bans clients that fetch the titles dump more than once a day
ANIDB_TITLES_MAX_AGE = 7 * 24 * 3600
ANIME_LIST_MAX_AGE = 3 * 24 * 3600

FEED_URL = "https://feed.animetosho.net/json"
FEED_MAX_PAGES = 4
FEED_MAX_AGE = 12 * 3600
DETAIL_MAX_AGE = 7 * 24 * 3600
DETAIL_WORKERS = 6
TOSHO_CACHE_DIR = os.path.join(CACHE_DIR, "animetosho")


def _normalize(title):
    title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    title = re.sub(r"[^a-z0-9]+", " ", title.lower())
    return " ".join(title.split())


def _cached_download(url, filename, max_age, timeout=60):
    """Return the cached file path, refreshing it when older than max_age."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, filename)
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age
    if not fresh:
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
        except Exception as e:
            # Keep using a stale copy rather than failing
            if not os.path.exists(path):
                raise
            logger.warning("Could not refresh %s, using cached copy: %s", filename, e)
    return path


class AnimeMapper:
    """Resolves (series title, TVDB season, TVDB episode) -> AniDB ids."""

    _lock = threading.Lock()
    _instance = None

    @classmethod
    def get(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self._titles = None   # normalized title -> set(aid)
        self._entries = None  # aid -> mapping dict
        self._by_tvdb = None  # tvdbid -> [aid]

    def _load(self):
        if self._titles is not None:
            return
        titles = {}
        path = _cached_download(ANIDB_TITLES_URL, "anime-titles.xml.gz", ANIDB_TITLES_MAX_AGE)
        with gzip.open(path, "rb") as f:
            for anime in ET.parse(f).getroot():
                aid = int(anime.get("aid"))
                for t in anime:
                    if t.text:
                        titles.setdefault(_normalize(t.text), set()).add(aid)

        entries, by_tvdb = {}, {}
        path = _cached_download(ANIME_LIST_URL, "anime-list-master.xml", ANIME_LIST_MAX_AGE)
        for anime in ET.parse(path).getroot():
            tvdbid = anime.get("tvdbid") or ""
            if not tvdbid.isdigit():
                continue
            aid = int(anime.get("anidbid"))
            offset = anime.get("episodeoffset") or "0"
            mappings = []
            for m in anime.iter("mapping"):
                pairs = {}
                for pair in (m.text or "").strip(";").split(";"):
                    if "-" in pair:
                        a, _, b = pair.partition("-")
                        if a.isdigit():
                            for tv in b.split("+"):
                                if tv.isdigit():
                                    pairs[int(tv)] = int(a)
                mappings.append({
                    "anidbseason": m.get("anidbseason"),
                    "tvdbseason": m.get("tvdbseason"),
                    "start": int(m.get("start")) if m.get("start") else None,
                    "end": int(m.get("end")) if m.get("end") else None,
                    "offset": int(m.get("offset") or 0),
                    "pairs": pairs,
                })
            entries[aid] = {
                "tvdbid": int(tvdbid),
                "season": anime.get("defaulttvdbseason"),
                "offset": int(offset) if offset.lstrip("-").isdigit() else 0,
                "mappings": mappings,
            }
            by_tvdb.setdefault(int(tvdbid), []).append(aid)

        self._titles, self._entries, self._by_tvdb = titles, entries, by_tvdb

    def find_tvdb_ids(self, title):
        self._load()
        aids = self._titles.get(_normalize(title), set())
        return {self._entries[a]["tvdbid"] for a in aids if a in self._entries}

    def resolve(self, tvdbid, season, episode):
        """Return (aid, anidb_episode) for a TVDB season/episode, or None."""
        self._load()
        best = None
        for aid in self._by_tvdb.get(tvdbid, []):
            entry = self._entries[aid]
            # Explicit mappings take precedence
            for m in entry["mappings"]:
                if m["anidbseason"] != "1" or m["tvdbseason"] != str(season):
                    continue
                if episode in m["pairs"]:
                    return aid, m["pairs"][episode]
                if m["start"] is not None:
                    ep = episode - m["offset"]
                    if m["start"] <= ep <= (m["end"] or ep):
                        return aid, ep
            if entry["season"] != str(season):
                continue
            ep = episode - entry["offset"]
            if ep >= 1 and (best is None or entry["offset"] > best[2]):
                best = (aid, ep, entry["offset"])
        return (best[0], best[1]) if best else None

    def resolve_special(self, tvdbid, episode):
        """Return (aid, anidb_special_no, tvdb_season) for a TVDB S00 episode, or None."""
        self._load()
        for aid in self._by_tvdb.get(tvdbid, []):
            entry = self._entries[aid]
            for m in entry["mappings"]:
                if m["anidbseason"] != "0" or m["tvdbseason"] != "0":
                    continue
                if episode in m["pairs"]:
                    special = m["pairs"][episode]
                elif m["start"] is not None and m["start"] <= episode <= (m["end"] or episode):
                    special = episode + m["offset"]
                else:
                    continue
                if special >= 1 and entry["season"] and entry["season"].isdigit():
                    return aid, special, int(entry["season"])
        return None


def refine_anime(video):
    """Attach AniDB/TVDB ids to an Episode when its series is a known anime."""
    if not isinstance(video, Episode) or video.season is None or video.episode is None:
        return
    try:
        mapper = AnimeMapper.get()
        names = [video.series] + list(getattr(video, "alternative_series", None) or [])
        tvdb_ids = [t for name in names for t in mapper.find_tvdb_ids(name)]
        # Fall back to the id found by the metadata refiner (title in another language)
        if not tvdb_ids and getattr(video, "series_tvdb_id", None):
            tvdb_ids = [int(video.series_tvdb_id)]
        for tvdbid in dict.fromkeys(tvdb_ids):
            if video.season == 0:
                special = mapper.resolve_special(tvdbid, video.episode)
                if special:
                    # Kept apart from series_anidb_* so other providers don't read it
                    # as a regular episode number
                    video.series_tvdb_id = tvdbid
                    video.anidb_special = special
                    logger.info("Anime special: %s S00E%02d -> anidb %s special %s (season %s)",
                                video.series, video.episode, *special)
                    return
                continue
            resolved = mapper.resolve(tvdbid, video.season, video.episode)
            if resolved:
                video.series_tvdb_id = tvdbid
                video.series_anidb_id, video.series_anidb_episode_no = resolved
                logger.info("Anime match: %s S%02dE%02d -> tvdb %s, anidb %s ep %s",
                            video.series, video.season, video.episode,
                            tvdbid, *resolved)
                return
    except Exception as e:
        logger.warning("Anime mapping failed for %s: %s", video.series, e)


# AnimeTosho reports Spanish variants via the track name
_LATAM_RE = re.compile(r"latin|latino|lat\b|419|mexic", re.I)
_SIGNS_RE = re.compile(r"\bforced\b|signs|songs|carteles", re.I)
_SDH_RE = re.compile(r"\bsdh\b|\bcc\b|hearing", re.I)


def _track_language(info):
    code = info.get("language_code") or info.get("lang")
    if not code:
        return None
    try:
        lang = Language.fromietf(code) if "-" in code else Language(code)
    except Exception:
        try:
            lang = Language.fromalpha2(code)
        except Exception:
            return None
    name = info.get("name") or ""
    if lang.alpha3 == "spa" and not lang.country:
        # Release tracks are either Latin American or European Spanish
        lang = Language("spa", "MX" if _LATAM_RE.search(name) else "ES")
    if info.get("forced") or _SIGNS_RE.search(name):
        return Language.rebuild(lang, forced=True)
    if _SDH_RE.search(name):
        return Language.rebuild(lang, hi=True)
    return lang


_DASH_EPISODE_RE = re.compile(r"\s-\s*[\W_]?(\d{1,3})(?:v\d)?[\W_]?(?=\s|\[|\(|\.|$)")


@lru_cache(maxsize=20000)
def _guess_numbers(name):
    """(season, episode) parsed from a release/file name; guessit is slow, so cache it."""
    guess = guessit(name, {"type": "episode"})
    season, episode = guess.get("season"), guess.get("episode")
    if episode is None:
        # Fansub style "Title S2 - 12 [1080p]" that guessit misses
        m = _DASH_EPISODE_RE.search(name)
        if m:
            episode = int(m.group(1))
    if isinstance(season, list):
        season = tuple(season)
    if isinstance(episode, list):
        episode = tuple(episode)
    return season, episode


class AnimeToshoNetSubtitle(Subtitle):
    provider_name = "animetosho_net"
    hash_verifiable = False

    def __init__(self, language, download_url, release_info, track_name, codec):
        super().__init__(language, page_link=download_url, original_format=True)
        self.download_url = download_url
        self.release_info = release_info
        self.track_name = track_name
        self.format = (codec or "ass").lower()
        self.matches = set()

    @property
    def id(self):
        return self.download_url

    def get_matches(self, video):
        self.matches |= guess_matches(video, guessit(self.release_info, {"type": "episode"}))
        self.matches |= {"series", "season", "episode"}
        return self.matches


class AnimeToshoNetProvider(Provider):
    """Subtitle tracks extracted from anime releases indexed by AnimeTosho.net."""

    provider_name = "animetosho_net"
    subtitle_class = AnimeToshoNetSubtitle
    video_types = (Episode,)
    hash_verifiable = False

    languages = {Language(c) for c in (
        "ara", "deu", "eng", "fra", "ind", "ita", "jpn", "kor", "msa", "nld",
        "pol", "por", "rus", "spa", "tha", "tur", "vie", "zho",
    )}
    languages |= {Language("spa", "MX"), Language("spa", "ES"), Language("por", "BR")}
    languages |= {Language.rebuild(l, forced=True) for l in list(languages)}
    languages |= {Language.rebuild(l, hi=True) for l in list(languages)}

    # Feed and release details are shared across searches in the same session
    _feed_cache = {}
    _detail_cache = {}

    def __init__(self):
        self.session = None

    def initialize(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def terminate(self):
        self.session.close()

    def _json(self, params):
        r = self.session.get(FEED_URL, params=params, timeout=60)
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _disk_get(key, max_age):
        path = os.path.join(TOSHO_CACHE_DIR, key + ".json.gz")
        try:
            if time.time() - os.path.getmtime(path) < max_age:
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    return json.load(f)
        except (OSError, ValueError):
            pass
        return None

    @staticmethod
    def _disk_put(key, data):
        try:
            os.makedirs(TOSHO_CACHE_DIR, exist_ok=True)
            with gzip.open(os.path.join(TOSHO_CACHE_DIR, key + ".json.gz"), "wt",
                           encoding="utf-8") as f:
                json.dump(data, f)
        except OSError as e:
            logger.debug("AnimeTosho cache write failed: %s", e)

    def _entries(self, aid):
        if aid not in self._feed_cache:
            key = f"feed_{aid}"
            entries = self._disk_get(key, FEED_MAX_AGE)
            if entries is None:
                entries = []
                for page in range(1, FEED_MAX_PAGES + 1):
                    batch = self._json({"aid": aid, "page": page})
                    entries.extend(e for e in batch if e.get("status") == "complete")
                    if len(batch) < 75:
                        break
                self._disk_put(key, entries)
            self._feed_cache[aid] = entries
        return self._feed_cache[aid]

    def _detail(self, torrent_id):
        if torrent_id not in self._detail_cache:
            key = f"torrent_{torrent_id}"
            detail = self._disk_get(key, DETAIL_MAX_AGE)
            if detail is None:
                detail = self._json({"show": "torrent", "id": torrent_id})
                # Only what we use: mediainfo makes these files huge
                for f in detail.get("files") or []:
                    f.pop("info", None)
                    f.pop("links", None)
                    f.pop("links_audio", None)
                    f.pop("screenshots", None)
                self._disk_put(key, detail)
            self._detail_cache[torrent_id] = detail
        return self._detail_cache[torrent_id]

    @staticmethod
    def _episode_matches(name, season, episode, anidb_ep, same_aid):
        """True if a release/file name refers to the wanted episode, None if unknown."""
        g_season, ep = _guess_numbers(name)
        if ep is None:
            return None
        eps = list(ep) if isinstance(ep, tuple) else [ep]
        if g_season is not None:
            seasons = list(g_season) if isinstance(g_season, tuple) else [g_season]
            if season in seasons and episode in eps:
                return True
            # "Part 2 - 01" style names get parsed as season 2 sometimes
            return same_aid and anidb_ep in eps and len(eps) == 1 and season in seasons
        # Absolute numbering inside the AniDB entry (fansub style "Title - 01")
        return same_aid and anidb_ep in eps

    def list_subtitles(self, video, languages):
        aid = getattr(video, "series_anidb_id", None)
        anidb_ep = getattr(video, "series_anidb_episode_no", None)
        season, episode = video.season, video.episode
        special = getattr(video, "anidb_special", None)
        if special:
            aid, special_no, season = special
            # Releases only name the first special consistently: "S02E00" / "- 00"
            if special_no != 1:
                logger.debug("Skipping %r: special %s has no release numbering", video, special_no)
                return []
            episode = anidb_ep = 0
        if not aid or anidb_ep is None:
            logger.debug("Skipping %r: no AniDB mapping", video)
            return []

        parsed = [(e, self._episode_matches(e.get("title", ""), season,
                                            episode, anidb_ep, True))
                  for e in self._entries(aid)]
        # Single-episode releases carry the AniDB episode id: learn it from the ones
        # whose title clearly matches, then drop releases of other episodes
        target_eids = {e["anidb_eid"] for e, hit in parsed
                       if hit and e.get("num_files") == 1 and e.get("anidb_eid")}
        candidates = []
        for entry, hit in parsed:
            if hit is False:
                continue
            eid = entry.get("anidb_eid")
            if hit is None and entry.get("num_files") == 1 and eid                     and target_eids and eid not in target_eids:
                continue
            # Batches have no single episode number in the title: inspect their files
            candidates.append(entry["id"])

        with ThreadPoolExecutor(DETAIL_WORKERS) as pool:
            details = list(pool.map(self._safe_detail, candidates))

        subtitles, seen = [], set()
        for detail in filter(None, details):
            same_aid = detail.get("anidb_aid") in (None, aid)
            for f in detail.get("files") or []:
                filename = f.get("filename") or ""
                if not self._episode_matches(filename, season, episode, anidb_ep, same_aid):
                    continue
                for att in f.get("attachments") or []:
                    if att.get("type") != "subtitle" or not att.get("url"):
                        continue
                    info = att.get("info") or {}
                    lang = _track_language(info)
                    if lang is None or lang not in languages or att["url"] in seen:
                        continue
                    seen.add(att["url"])
                    subtitles.append(self.subtitle_class(
                        lang, att["url"], filename,
                        info.get("name") or "", info.get("format") or info.get("codec"),
                    ))
        logger.info("AnimeTosho.net: %d subtitles for %r", len(subtitles), video)
        return subtitles

    def _safe_detail(self, torrent_id):
        try:
            return self._detail(torrent_id)
        except Exception as e:
            logger.debug("AnimeTosho.net detail %s failed: %s", torrent_id, e)
            return None

    def download_subtitle(self, subtitle):
        r = self.session.get(subtitle.download_url, timeout=30)
        r.raise_for_status()
        content = r.content
        if content.startswith(b"\xfd7zXZ\x00"):
            content = lzma.decompress(content)
        subtitle.content = content
        return subtitle
