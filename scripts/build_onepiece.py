#!/usr/bin/env python3
"""Build the One Piece index: English cards + official Chinese names.

English side: punk-records (github.com/buhbbl/punk-records), the vegapull dump
of the official EN card list, with hotlinkable official card scans.

Chinese side: the official CN site's own API (webadmin.windoent.com/op-public).
Card numbers are identical across languages, so weblist gives every CN print
row and webInfo/{id} the official Chinese card name. Names are cached in
data/onepiece_zh.json so a rebuild only fetches numbers it has not seen.

Writes data/onepiece_cards.json, data/onepiece_sets.json, data/onepiece_zh.json.
Be polite: the CN API is the production backend of the official site.
"""

import json
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

PUNK = "https://raw.githubusercontent.com/buhbbl/punk-records/main/english"
CN = "https://webadmin.windoent.com/op-public"
OUT = Path(__file__).resolve().parent.parent / "data"
UA = "cn-card-finder bake (+https://github.com/shizukaziye/cn-card-finder)"
DELAY = 0.35


def get(url, tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)


def cn_rows():
    page, rows = 1, []
    while True:
        d = get(f"{CN}/cardList/cardlist/weblist?page={page}&limit=500")["page"]
        rows.extend(d["list"])
        if page >= d["totalPage"]:
            return rows
        page += 1
        time.sleep(DELAY)


def main():
    packs = get(f"{PUNK}/packs.json")
    by_id = get(f"{PUNK}/index/cards_by_id.json")

    zh_path = OUT / "onepiece_zh.json"
    zh = json.loads(zh_path.read_text()) if zh_path.exists() else {}

    rows = cn_rows()
    print(f"CN print rows: {len(rows)}", flush=True)
    best = {}                       # number -> lowest id (earliest entry)
    for r in rows:
        num = r["cardNumber"].strip()
        # P-suffixed rows are alt arts of the base number with the same name.
        if not num or num.endswith("P"):
            continue
        if num not in best or r["id"] < best[num]:
            best[num] = r["id"]

    todo = sorted(n for n in best if n not in zh)
    print(f"unique CN numbers: {len(best)}, new to fetch: {len(todo)}", flush=True)
    lock = threading.Lock()
    done = [0]
    local = threading.local()       # one keep-alive session per worker

    def fetch_one(num):
        if not hasattr(local, "s"):
            local.s = requests.Session()
            local.s.headers["User-Agent"] = UA
        name = ""
        for attempt in range(3):
            try:
                r = local.s.get(f"{CN}/cardList/cardlist/webInfo/{best[num]}",
                                timeout=30)
                name = ((r.json().get("info") or {}).get("cardName") or "").strip()
                break
            except Exception as exc:
                if attempt == 2:
                    print(f"  {num}: {exc}", flush=True)
                else:
                    time.sleep(3 * (attempt + 1))
        time.sleep(0.4)
        with lock:
            if name:
                zh[num] = name
            done[0] += 1
            if done[0] % 200 == 0:
                print(f"  {done[0]}/{len(todo)}", flush=True)
                zh_path.write_text(json.dumps(zh, ensure_ascii=False,
                                              separators=(",", ":"), sort_keys=True),
                                   encoding="utf-8")

    # Two slow workers: this is the official site's production backend, and it
    # 504s under anything faster.
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(fetch_one, todo))
    zh_path.write_text(json.dumps(zh, ensure_ascii=False, separators=(",", ":"),
                                  sort_keys=True), encoding="utf-8")

    # one entry per base card number; count art variants (_p1, _p2, …)
    cards, variants = {}, {}
    for cid, c in by_id.items():
        m = re.match(r"^(.*?)(_p\d+)?$", cid)
        base = m.group(1)
        if m.group(2):
            variants[base] = variants.get(base, 0) + 1
            continue
        pack = packs.get(str(c.get("pack_id")), {})
        label = (pack.get("title_parts") or {}).get("label") or ""
        cards[base] = {
            "i": base, "n": c.get("name") or "", "l": base,
            "s": label, "r": c.get("rarity") or "",
            "u": (c.get("img_url") or "").split("?")[0],
        }
    for base, n in variants.items():
        if base in cards:
            cards[base]["v"] = n
    for num, name in zh.items():
        if num in cards:
            cards[num]["zh"] = name

    out = sorted(cards.values(), key=lambda c: c["i"])
    if len(out) < 1500:
        raise SystemExit(f"only {len(out)} cards; refusing to write")

    seen, sets = set(), []
    for p in packs.values():
        tp = p.get("title_parts") or {}
        label = tp.get("label") or ""
        if label and label not in seen:
            seen.add(label)
            sets.append({"i": label, "n": f"{tp.get('title', '')} [{label}]"})
    sets.sort(key=lambda s: s["i"])

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "onepiece_cards.json").write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (OUT / "onepiece_sets.json").write_text(
        json.dumps(sets, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    zh_cov = sum(1 for c in out if c.get("zh"))
    print(f"wrote {len(out)} cards ({zh_cov} with CN names), {len(sets)} sets")


if __name__ == "__main__":
    main()
