#!/usr/bin/env python3
"""Dump the mainland (简中) Pokemon card catalogue from Cryst's card DB.

tcg.mik.moe is the community database of every simplified-Chinese print.
card-advance-search with no filter pages through the whole catalogue
(~12.5k print rows). We group prints by Chinese card name so the app can
show "this card exists in 简中 as CSV9C 221/208 SR, …" next to a derived name.

Writes data/pokemon_cn_prints.json  {cnName: [[setCode, index, rarity], ...]}
and    data/pokemon_cn_sets.json    {setCode: {n: name, d: date}}
Be polite: ~2 requests/second against a small community site.
"""

import json
import time
import urllib.request
from pathlib import Path

API = "https://tcg.mik.moe/api/v3/card"
OUT = Path(__file__).resolve().parent.parent / "data"
UA = "cn-card-finder bake (+https://github.com/shizukaziye/cn-card-finder)"
DELAY = 0.45


def post(path, body, tries=4):
    data = json.dumps(body).encode()
    for attempt in range(tries):
        try:
            req = urllib.request.Request(f"{API}/{path}", data=data, headers={
                "User-Agent": UA, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                out = json.loads(resp.read().decode())
            if out.get("code") != 200:
                raise RuntimeError(f"{path}: {str(out)[:200]}")
            return out["data"]
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)


def main():
    sets = {}
    for s in post("product-list", {})["list"]:
        sets[s["setCode"]] = {"n": s["name"], "d": (s.get("releaseDate") or "")[:10]}

    rows, page = [], 1
    while True:
        d = post("card-advance-search", {"Page": page, "PageSize": 100})
        rows.extend(d["list"])
        if page >= d["pageNum"]:
            break
        page += 1
        if page % 20 == 0:
            print(f"  page {page}/{d['pageNum']}")
        time.sleep(DELAY)

    if len(rows) < 10000:
        raise SystemExit(f"only {len(rows)} print rows; refusing to write")

    prints = {}
    for r in rows:
        prints.setdefault(r["cardName"], []).append(
            [r["setCode"], r["cardIndex"], r["rarity"]])
    for v in prints.values():
        v.sort(key=lambda p: (p[0], p[1]))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pokemon_cn_prints.json").write_text(
        json.dumps(prints, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "pokemon_cn_sets.json").write_text(
        json.dumps(sets, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(rows)} prints of {len(prints)} distinct names, {len(sets)} sets")


if __name__ == "__main__":
    main()
