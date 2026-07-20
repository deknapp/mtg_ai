"""Arena log importer: find the MTG Arena Player.log and read the sealed pool out of it.

Arena writes the sealed pool to its log as a `"CardPool": [<grpId>, ...]` array once the
player has "Detailed Logs (Plugin Support)" enabled. Each grpId is the card's Arena id, which
maps 1:1 to Scryfall's `arena_id` — so the pool resolves by id, no OCR and no name matching.

This module only extracts ids + metadata; turning ids into cards is enrichment's job.
"""

from __future__ import annotations

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


def parse_pool(text: str) -> ParsedPool:
    """Extract the sealed pool from raw Arena log text.

    Picks the largest `CardPool` array (the complete pool; the log also emits shrinking pools
    as cards move to the deck/sideboard). Reads the most recent sealed event name and the
    detailed-logging status so callers can give a precise hint when the pool is missing.
    """
    detailed = None
    if _DETAILED_ON in text:
        detailed = True
    elif _DETAILED_OFF in text:
        detailed = False

    pools = [
        [int(x) for x in body.split(",") if x.strip()]
        for body in _CARDPOOL_RE.findall(text)
    ]
    events = _EVENT_RE.findall(text)
    event = events[-1] if events else None

    if not pools:
        return ParsedPool(grp_ids=[], event=event, set_code=_set_from_event(event),
                          detailed_logs=detailed)

    grp_ids = max(pools, key=len)
    return ParsedPool(
        grp_ids=grp_ids,
        event=event,
        set_code=_set_from_event(event),
        detailed_logs=detailed,
    )


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
    if not parsed.grp_ids:
        hint = (
            "Enable Arena → Settings → Account → 'Detailed Logs (Plugin Support)', fully quit "
            "(Cmd+Q) and reopen Arena, then open your sealed event."
            if parsed.detailed_logs is not True
            else "Open your sealed event in Arena so the pool is written to the log."
        )
        raise ArenaLogError(f"No sealed CardPool found in {path}.\n{hint}")
    return parsed
