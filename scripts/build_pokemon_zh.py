#!/usr/bin/env python3
"""Build the English -> simplified-Chinese Pokemon species map.

Source: PokeAPI's CSV data on GitHub. Language 9 is English, 12 is zh-Hans.
Writes data/pokemon_zh_species.json as {"Bulbasaur": "妙蛙种子", ...}.
"""

import csv
import io
import json
import urllib.request
from pathlib import Path

CSV_URL = ("https://raw.githubusercontent.com/PokeAPI/pokeapi/master/"
           "data/v2/csv/pokemon_species_names.csv")
OUT = Path(__file__).resolve().parent.parent / "data" / "pokemon_zh_species.json"

EN, ZH_HANS = "9", "12"


def main():
    with urllib.request.urlopen(CSV_URL, timeout=60) as resp:
        text = resp.read().decode("utf-8")

    en, zh = {}, {}
    for row in csv.DictReader(io.StringIO(text)):
        sid = row["pokemon_species_id"]
        lang = row["local_language_id"]
        if lang == EN:
            en[sid] = row["name"]
        elif lang == ZH_HANS:
            zh[sid] = row["name"]

    mapping = {en[sid]: zh[sid] for sid in en if sid in zh}
    missing = [en[sid] for sid in en if sid not in zh]
    if missing:
        print(f"note: {len(missing)} species lack zh-Hans names: {missing[:10]}")
    if len(mapping) < 1000:
        raise SystemExit(f"only {len(mapping)} names mapped; refusing to write")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(mapping, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"wrote {OUT} with {len(mapping)} species")


if __name__ == "__main__":
    main()
