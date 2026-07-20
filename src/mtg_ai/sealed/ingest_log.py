"""Arena log importer: find the MTG Arena Player.log and read the sealed pool out of it.

Arena writes the sealed pool to its log as a `"CardPool": [<grpId>, ...]` array once the
player has "Detailed Logs (Plugin Support)" enabled. Each grpId is the card's Arena id, which
maps 1:1 to Scryfall's `arena_id` — so the pool resolves by id, no OCR and no name matching.

This module only extracts ids + metadata; turning ids into cards is enrichment's job.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Standard macOS location; Player-prev.log is the rotated previous session.
_DEFAULT_LOGS = [
    "~/Library/Logs/Wizards Of The Coast/MTGA/Player.log",
    "~/Library/Logs/Wizards Of The Coast/MTGA/Player-prev.log",
]

_CARDPOOL_RE = re.compile(r'"CardPool"\s*:\s*\[([0-9,\s]*)\]')
_EVENT_RE = re.compile(r'"InternalEventName"\s*:\s*"([^"]*[Ss]ealed[^"]*)"')
# Arena stamps each logger block with a wall-clock line, e.g.
#   [UnityCrossThreadLogger]7/20/2026 8:12:39 AM
_TIMESTAMP_RE = re.compile(r'\[UnityCrossThreadLogger\]([0-9]{1,2}/[0-9]{1,2}/[0-9]{4} [0-9:]+ [AP]M)')
# e.g. ArenaDirect_MSH_Play_Sealed_20260717 -> set code MSH
_SET_RE = re.compile(r'(?:ArenaDirect|Sealed)_([A-Za-z0-9]{2,5})_')
_DETAILED_ON = "DETAILED LOGS: ENABLED"
_DETAILED_OFF = "DETAILED LOGS: DISABLED"


class ArenaLogError(RuntimeError):
    """Raised when a sealed pool can't be read from the Arena log."""


@dataclass
class ParsedPool:
    grp_ids: list[int]
    event: str | None = None
    set_code: str | None = None
    detailed_logs: bool | None = None  # None = unknown (no status line seen)
    timestamp: str | None = None  # wall-clock of the pool's first appearance in the log
    notes: list[str] = field(default_factory=list)


def find_arena_log(candidates: list[str] | None = None) -> Path | None:
    """Return the first existing Arena log path, or None if none is found."""
    for raw in candidates or _DEFAULT_LOGS:
        p = Path(raw).expanduser()
        if p.exists():
            return p
    return None


def _set_from_event(event: str | None) -> str | None:
    if not event:
        return None
    m = _SET_RE.search(event)
    return m.group(1).lower() if m else None


def detailed_logs_status(text: str) -> bool | None:
    """Whether Arena's 'Detailed Logs (Plugin Support)' was on. None = no status line seen."""
    if _DETAILED_ON in text:
        return True
    if _DETAILED_OFF in text:
        return False
    return None


def _nearest_before(marks: list[tuple[int, str]], pos: int) -> str | None:
    """The value of the last (position, value) mark occurring before `pos` (marks are sorted)."""
    found = None
    for mark_pos, value in marks:
        if mark_pos < pos:
            found = value
        else:
            break
    return found


def list_pools(text: str) -> list[ParsedPool]:
    """Every distinct *complete* sealed pool in the log, most-recently-active first.

    Arena re-emits the pool many times, and emits shrinking `CardPool` arrays as cards move into
    the deck, so a raw scan is full of duplicates and partial pools. A complete pool is the
    largest one Arena logged; we keep only arrays of that maximum length (which drops every
    fragment regardless of set/pool size), de-duplicate by contents, and tag each survivor with
    the wall-clock timestamp and sealed event nearest *before* its first appearance — the metadata
    a person needs to tell two same-size pools apart and pick the right one.

    Ordered newest-first (the log is append-only, so a later file position = more recent), so
    index 0 is "your latest pool".
    """
    detailed = detailed_logs_status(text)
    timestamps = [(m.start(), m.group(1)) for m in _TIMESTAMP_RE.finditer(text)]
    events = [(m.start(), m.group(1)) for m in _EVENT_RE.finditer(text)]

    raw = [
        (m.start(), [int(x) for x in m.group(1).split(",") if x.strip()])
        for m in _CARDPOOL_RE.finditer(text)
    ]
    raw = [(pos, ids) for pos, ids in raw if ids]
    if not raw:
        return []
    full_len = max(len(ids) for _, ids in raw)

    index_of: dict[tuple[int, ...], int] = {}
    pools: list[ParsedPool] = []
    last_seen_pos: list[int] = []
    for pos, ids in raw:
        if len(ids) != full_len:  # a shrinking/partial emission, not the complete pool
            continue
        key = tuple(sorted(ids))
        if key in index_of:
            last_seen_pos[index_of[key]] = pos  # remember its most recent sighting
            continue
        event = _nearest_before(events, pos)
        index_of[key] = len(pools)
        pools.append(
            ParsedPool(
                grp_ids=ids,
                event=event,
                set_code=_set_from_event(event),
                detailed_logs=detailed,
                timestamp=_nearest_before(timestamps, pos),
            )
        )
        last_seen_pos.append(pos)

    order = sorted(range(len(pools)), key=lambda i: last_seen_pos[i], reverse=True)
    return [pools[i] for i in order]


def parse_pool(text: str) -> ParsedPool:
    """Extract a single sealed pool from raw Arena log text.

    Returns the most recently active full pool (see `list_pools`) — use `list_pools` directly
    when the caller wants to show all of them and let the user choose. Reads the detailed-logging
    status and event name so callers can give a precise hint when no pool is present.
    """
    detailed = detailed_logs_status(text)
    pools = list_pools(text)
    if not pools:
        event = (_EVENT_RE.findall(text) or [None])[-1]
        return ParsedPool(grp_ids=[], event=event, set_code=_set_from_event(event),
                          detailed_logs=detailed)
    # Back-compat single-pool API: return the most recently active pool (list_pools' first),
    # not the largest — a newer, equal-or-smaller pool used to lose to a stale bigger one.
    return pools[0]


def load_pool(log_path: str | Path | None = None) -> ParsedPool:
    """Find (or use the given) Arena log and parse the sealed pool from it.

    Raises ArenaLogError with an actionable message when the log is missing or the pool isn't
    present (usually because Detailed Logs are off or no sealed event has been opened).
    """
    path = Path(log_path).expanduser() if log_path else find_arena_log()
    if path is None or not path.exists():
        raise ArenaLogError(
            "Could not find the MTG Arena log. Expected it at\n  "
            + _DEFAULT_LOGS[0]
            + "\nOpen Arena at least once, or pass the log path explicitly."
        )
    parsed = parse_pool(path.read_text(errors="ignore"))
    return _require_pool(parsed, path)


def _require_pool(parsed: ParsedPool, path: Path) -> ParsedPool:
    if not parsed.grp_ids:
        hint = (
            "Enable Arena → Settings → Account → 'Detailed Logs (Plugin Support)', fully quit "
            "(Cmd+Q) and reopen Arena, then open your sealed event."
            if parsed.detailed_logs is not True
            else "Open your sealed event in Arena so the pool is written to the log."
        )
        raise ArenaLogError(f"No sealed CardPool found in {path}.\n{hint}")
    return parsed


def load_pool_fixture(path: str | Path) -> ParsedPool:
    """Load a pool from a saved JSON fixture (raw grpIds + metadata). For offline demo/testing."""
    data = json.loads(Path(path).expanduser().read_text())
    return ParsedPool(
        grp_ids=data["grp_ids"],
        event=data.get("event"),
        set_code=data.get("set"),
        detailed_logs=True,
    )
