#!/usr/bin/env python3
"""Build the Riftbound index: English cards + official Chinese names.

English side: Riot's public gallery API (publishing-content.riotgames.com),
which serves every card with image URLs on the Sanity CDN.

Chinese side: the official CN site's backend (lol-api.playloltcg.com), which
returns the full simplified-Chinese catalogue in a few bulk calls. Chinese and
English printings share set codes and collector numbers (OGN-001/298 in EN is
OGN·001/298 in CN), so the normalized number is the join key. Official CN
names are not literal translations, so the join is the only correct mapping.

Writes data/riftbound_cards.json and data/riftbound_sets.json.
"""

import json
import time
import urllib.request
from pathlib import Path

EN_API = ("https://content.publishing.riotgames.com/publishing-content/v2.0/"
          "public/channel/riftbound_website/list/riftbound_gallery_cards"
          "?locale=en_US&from={start}&limit=200")
CN_API = "https://lol-api.playloltcg.com/xcx/card/searchCardCraftWeb"
OUT = Path(__file__).resolve().parent.parent / "data"
UA = "cn-card-finder bake (+https://github.com/shizukaziye/cn-card-finder)"

# Set names. The gallery API's set.label is the literal string "Card Set",
# so English names are pinned here; CN names from the official product list.
SET_EN = {"OGN": "Origins", "OGS": "Origins: Proving Grounds",
          "SFD": "Spiritforged", "UNL": "Unleashed", "VEN": "Vendetta",
          "RAD": "Radiance"}
SET_CN = {"OGN": "起源", "OGS": "起源：试炼场", "SFD": "铸魂淬炼",
          "UNL": "破限", "VEN": "化神争锋", "RAD": "辉耀群星"}


def fetch(url, body=None, tries=4):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"User-Agent": UA}
    if data:
        headers["Content-Type"] = "application/json"
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)


def norm_no(no):
    """'OGN·001/298' or 'OGN-001/298' -> 'OGN-001'; keeps alt-art suffixes."""
    if not no:
        return ""
    return no.replace("·", "-").split("/")[0].strip()


def main():
    en, start = [], 0
    while True:
        d = fetch(EN_API.format(start=start))
        items = d.get("data") or []
        en.extend(items)
        total = (d.get("metadata") or {}).get("totalItems") or 0
        start += len(items)
        if not items or start >= total:
            break
        time.sleep(0.4)
    print(f"EN cards: {len(en)}")

    zh, page = {}, 1
    while True:
        d = fetch(CN_API, {"pageNum": page, "pageSize": 500, "searchContent": "",
                           "cardCategoryList": [], "cardColorList": [],
                           "rarityList": [], "productCodeList": []})
        rows = (d.get("result") or {}).get("list") or []
        for r in rows:
            key = norm_no(r.get("cardNo"))
            name = (r.get("cardName") or "").strip()
            sub = (r.get("subTitle") or "").strip()
            if sub:                       # champion cards: name + subtitle
                name = f"{name} {sub}"
            if key and name and key not in zh:
                zh[key] = name
        total = (d.get("result") or {}).get("total") or 0
        if page * 500 >= total or not rows:
            break
        page += 1
        time.sleep(0.4)
    print(f"CN names: {len(zh)}")

    cards, seen_sets = [], {}
    for c in en:
        code = norm_no(c.get("publicCode"))
        if not code:
            continue
        set_id = (c.get("set") or {}).get("id") or code.split("-")[0]
        set_id = str(set_id).upper()
        seen_sets.setdefault(set_id, (c.get("set") or {}).get("label") or set_id)
        img = ((c.get("cardImage") or {}).get("url")) or ""
        rarity = c.get("rarity") or {}
        if isinstance(rarity, dict):          # {"label":"Rarity","value":{"label":"Common",…}}
            rarity = ((rarity.get("value") or {}).get("label")) or ""
        artist = c.get("a") or c.get("illustrator") or {}
        if isinstance(artist, dict):
            vals = artist.get("values") or []
            artist = (vals[0].get("label") if vals else "") or ""
        card = {
            "i": code, "n": c.get("name") or "", "l": c.get("publicCode") or code,
            "s": set_id, "r": rarity, "u": img,
        }
        if artist:
            card["a"] = artist
        if code in zh:
            card["zh"] = zh[code]
        cards.append(card)

    cards.sort(key=lambda c: c["i"])
    if len(cards) < 1000:
        raise SystemExit(f"only {len(cards)} cards; refusing to write")

    dupes = len(cards) - len({c["i"] for c in cards})
    if dupes:
        print(f"note: {dupes} duplicate codes kept (variant rows)")
    unmatched = sum(1 for c in cards if "zh" not in c)
    print(f"EN cards without a CN name: {unmatched}")

    sets = [{"i": sid,
             "n": SET_EN.get(sid, label if label != "Card Set" else sid)
                  + (f" {SET_CN[sid]}" if sid in SET_CN else "")}
            for sid, label in sorted(seen_sets.items())]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "riftbound_cards.json").write_text(
        json.dumps(cards, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "riftbound_sets.json").write_text(
        json.dumps(sets, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(cards)} cards ({len(cards) - unmatched} with CN names), "
          f"{len(sets)} sets")


if __name__ == "__main__":
    main()
