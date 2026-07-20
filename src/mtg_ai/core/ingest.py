"""Scryfall ingest: build the local SQLite card store.

Two modes:

    python -m mtg_ai.core.ingest              # full "oracle_cards" bulk (~100MB, all cards)
    python -m mtg_ai.core.ingest --set msh    # just one set (a sealed/draft pool; tiny, no bulk download)

Set-scoped mode is usually what you want: a sealed or draft pool is a single set, so scoping the
card DB to that set keeps enrichment focused and skips the 100MB fetch. Records carry `arena_id`,
so a sealed pool read from the Arena log resolves by id.

Scryfall data is free to use within their guidelines. We stream the bulk download rather than
buffering it, page the search API politely, and identify ourselves with a User-Agent per their
API etiquette.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request

from .config import get_settings
from .data import build_sqlite

BULK_META_URL = "https://api.scryfall.com/bulk-data"
SEARCH_URL = "https://api.scryfall.com/cards/search"
_HEADERS = {"User-Agent": "mtg_ai/0.1", "Accept": "application/json"}


def bulk_download_uri(kind: str = "oracle_cards") -> str:
    """Resolve the current download URI for a Scryfall bulk-data kind."""
    req = urllib.request.Request(BULK_META_URL, headers=_HEADERS)
    with urllib.request.urlopen(req) as resp:
        meta = json.load(resp)
    for item in meta["data"]:
        if item["type"] == kind:
            return item["download_uri"]
    raise ValueError(f"Scryfall bulk kind {kind!r} not found")


def stream_cards(uri: str):
    """Yield card records from the bulk JSON array without buffering the whole file."""
    import ijson  # optional, streaming parser; only needed for a real ingest

    req = urllib.request.Request(uri, headers=_HEADERS)
    with urllib.request.urlopen(req) as resp:
        yield from ijson.items(resp, "item")


def stream_set_cards(set_code: str):
    """Yield every card in one set by paging the Scryfall search API.

    `unique=prints` is unnecessary for a draft pool; we use the default (one row per card in
    the set). Follows `next_page` until `has_more` is false, staying within one set.
    """
    query = urllib.parse.urlencode({"q": f"set:{set_code}", "unique": "cards", "order": "set"})
    url: str | None = f"{SEARCH_URL}?{query}"
    while url:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req) as resp:
            page = json.load(resp)
        yield from page.get("data", [])
        url = page.get("next_page") if page.get("has_more") else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the local Scryfall card store.")
    parser.add_argument(
        "--set", dest="set_code", default=None,
        help="Ingest only this set code (e.g. 'msh'). Omit for the full oracle_cards bulk.",
    )
    ns = parser.parse_args()
    settings = get_settings()

    if ns.set_code:
        code = ns.set_code.lower()
        print(f"Fetching set {code!r} from Scryfall search API\n  -> {settings.db_path}")
        count = build_sqlite(settings.db_path, stream_set_cards(code))
        print(f"Ingested {count} cards from set {code!r} into {settings.db_path}")
    else:
        print("Resolving Scryfall bulk-data URI...")
        uri = bulk_download_uri("oracle_cards")
        print(f"Streaming {uri}\n  -> {settings.db_path}")
        count = build_sqlite(settings.db_path, stream_cards(uri))
        print(f"Ingested {count} cards into {settings.db_path}")


if __name__ == "__main__":
    main()
