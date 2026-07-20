"""17Lands card-ratings: fetch, local cache, and the Sealed -> Limited fallback ladder.

17Lands publishes public per-card stats per (set, format). GIH win-rate (games-in-hand win
rate, `ever_drawn_win_rate`) is the standard card-power proxy. We cache rows in a local SQLite
DB so builds are offline and fast; `reload()` re-fetches (the app's "reload 17Lands data").

For a freshly released set the requested format (Sealed) may have no win-rate data yet even
though 17Lands is logging games — so `get()` falls back to the set's Limited/draft data and,
failing that, reports no signal. Rows carry `mtga_id` (= Arena grpId) so ratings join to a pool
by id, not by name.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CARD_RATINGS_URL = "https://www.17lands.com/card_ratings/data"
UA = "mtg_ai/0.1 (personal sealed deck builder)"

# API column -> our column.
FIELD_MAP = {
    "name": "name",
    "mtga_id": "mtga_id",
    "rarity": "rarity",
    "color": "color",
    "seen_count": "seen_count",
    "avg_seen": "alsa",
    "game_count": "game_count",
    "win_rate": "win_rate",
    "ever_drawn_game_count": "gih_count",
    "ever_drawn_win_rate": "gih_wr",
    "drawn_improvement_win_rate": "iwd",
}

# Try the real format first, then infer from Limited/draft, then give up.
FALLBACK_LADDER = {
    "Sealed": ["Sealed", "PremierDraft", "TradDraft", "QuickDraft"],
    "TradSealed": ["TradSealed", "Sealed", "PremierDraft"],
    "PremierDraft": ["PremierDraft", "QuickDraft"],
}


@dataclass
class RatingsResult:
    requested_format: str
    source_format: str  # which format actually supplied usable data (differs => fallback used)
    rows: list[dict]
    usable: bool

    def by_arena_id(self) -> dict[int, float]:
        """Map Arena id -> GIH win-rate for rows that have a win-rate."""
        return {r["mtga_id"]: r["gih_wr"] for r in self.rows
                if r.get("mtga_id") is not None and r.get("gih_wr") is not None}


class RatingsCache:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(Path(db_path).expanduser())
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                """CREATE TABLE IF NOT EXISTS card_ratings (
                    set_code TEXT, format TEXT, name TEXT, mtga_id INTEGER,
                    rarity TEXT, color TEXT, seen_count INTEGER, alsa REAL,
                    game_count INTEGER, win_rate REAL, gih_count INTEGER, gih_wr REAL, iwd REAL,
                    fetched_at TEXT,
                    PRIMARY KEY (set_code, format, name))"""
            )
            con.execute(
                """CREATE TABLE IF NOT EXISTS fetch_meta (
                    set_code TEXT, format TEXT, rows INTEGER, rows_with_winrate INTEGER,
                    fetched_at TEXT, url TEXT, PRIMARY KEY (set_code, format))"""
            )

    # --- network ---------------------------------------------------------------
    @staticmethod
    def _fetch_raw(set_code: str, fmt: str) -> list[dict]:
        url = f"{CARD_RATINGS_URL}?expansion={set_code.upper()}&format={fmt}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
            return json.loads(resp.read().decode("utf-8"))

    def reload(self, set_code: str, fmt: str) -> int:
        """Fetch (set, fmt) from 17Lands and upsert into the cache. Returns row count."""
        raw = self._fetch_raw(set_code, fmt)
        rows = [{ours: r.get(api) for api, ours in FIELD_MAP.items()} for r in raw]
        with_wr = sum(1 for r in rows if r["gih_wr"] is not None)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with sqlite3.connect(self.db_path) as con:
            con.execute("DELETE FROM card_ratings WHERE set_code=? AND format=?", (set_code, fmt))
            con.executemany(
                """INSERT OR REPLACE INTO card_ratings
                   (set_code, format, name, mtga_id, rarity, color, seen_count, alsa,
                    game_count, win_rate, gih_count, gih_wr, iwd, fetched_at)
                   VALUES (:set_code,:format,:name,:mtga_id,:rarity,:color,:seen_count,:alsa,
                    :game_count,:win_rate,:gih_count,:gih_wr,:iwd,:fetched_at)""",
                [{**r, "set_code": set_code, "format": fmt, "fetched_at": now} for r in rows],
            )
            con.execute(
                """INSERT OR REPLACE INTO fetch_meta
                   (set_code, format, rows, rows_with_winrate, fetched_at, url) VALUES (?,?,?,?,?,?)""",
                (set_code, fmt, len(rows), with_wr, now,
                 f"{CARD_RATINGS_URL}?expansion={set_code.upper()}&format={fmt}"),
            )
        return len(rows)

    # --- cache reads -----------------------------------------------------------
    def _read(self, set_code: str, fmt: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as con:
            con.row_factory = sqlite3.Row
            cur = con.execute(
                "SELECT * FROM card_ratings WHERE set_code=? AND format=?", (set_code, fmt)
            )
            return [dict(r) for r in cur.fetchall()]

    def is_cached(self, set_code: str, fmt: str) -> bool:
        return bool(self._read(set_code, fmt))

    @staticmethod
    def _usable(rows: list[dict]) -> bool:
        return any(r.get("gih_wr") is not None for r in rows)

    def get(self, set_code: str, fmt: str = "Sealed") -> RatingsResult:
        """Read ratings from cache, applying the Sealed->Limited fallback ladder. No network."""
        for candidate in FALLBACK_LADDER.get(fmt, [fmt]):
            rows = self._read(set_code, candidate)
            if rows and self._usable(rows):
                return RatingsResult(fmt, candidate, rows, True)
        return RatingsResult(fmt, fmt, self._read(set_code, fmt), False)

    def ensure(self, set_code: str, fmt: str = "Sealed", *, reload: bool = False) -> RatingsResult:
        """Guarantee ratings are cached (fetching the whole fallback ladder if needed), then get().

        Network is used only when the needed formats aren't cached yet (or reload=True).
        """
        for candidate in FALLBACK_LADDER.get(fmt, [fmt]):
            if reload or not self.is_cached(set_code, candidate):
                try:
                    self.reload(set_code, candidate)
                except Exception:  # noqa: BLE001 - offline / rate-limited: fall through to cache
                    pass
            if self._usable(self._read(set_code, candidate)):
                break
        return self.get(set_code, fmt)
