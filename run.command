#!/bin/bash
# Double-click this in Finder to launch the MTG AI sealed deck builder.
# Builds the web UI on first run, serves it locally, and opens your browser.
cd "$(dirname "$0")" || exit 1
export PATH="$HOME/.local/bin:$PATH"
exec uv run mtg-ai
