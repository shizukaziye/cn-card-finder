#!/usr/bin/env python3
"""Build the Pokemon card index from michi-binder's.

michi-binder (github.com/shizukaziye/michi-binder) rebuilds its TCGdex-based
index every Monday and verifies every image URL, so this repo just refetches
that index and drops what a card buyer cannot use: the TCG Pocket digital sets
(asset URLs under /tcgp/), which exist only in the phone game.

Writes data/pokemon_cards.json and data/pokemon_sets.json.
"""

import json
import urllib.request
from pathlib import Path

RAW = "https://raw.githubusercontent.com/shizukaziye/michi-binder/main/data"
OUT = Path(__file__).resolve().parent.parent / "data"


def fetch(name):
    with urllib.request.urlopen(f"{RAW}/{name}", timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    cards = fetch("cards.json")
    sets = fetch("sets.json")

    kept = [c for c in cards if "/tcgp/" not in c.get("u", "")]
    kept_sets = {c["s"] for c in kept}
    sets = [s for s in sets if s["i"] in kept_sets]

    if len(kept) < 15000:
        raise SystemExit(f"only {len(kept)} cards after filtering; refusing to write")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pokemon_cards.json").write_text(
        json.dumps(kept, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "pokemon_sets.json").write_text(
        json.dumps(sets, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(kept)} cards ({len(cards) - len(kept)} TCG Pocket dropped), "
          f"{len(sets)} sets")


if __name__ == "__main__":
    main()
