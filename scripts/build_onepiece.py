#!/usr/bin/env python3
"""Build the One Piece index: English cards + official Chinese names.

English side: punk-records (github.com/buhbbl/punk-records), the vegapull dump
of the official EN card list, with hotlinkable official card scans.

Chinese side: the official CN site's own API. Since August 2026 it lives under
webadmin.windoent.com/front/op-public (the old /op-public path answers 403);
the site's axios client sends no token or special headers. Card numbers are
identical across languages, so weblist gives every CN print row and
webInfo/{id} the official Chinese card name. Names are cached in
data/onepiece_zh.json so a rebuild only fetches numbers it has not seen.

CN print rows mark alternate arts with a suffix on the card number: letters
(EB01-001P, EB01-006SP, OP01-016P-R) on older sets, _NN or -NN (OP17-001_02,
OP06-050-03) since OPC-12. base_number() folds all of them onto the base
number, which is what punk-records uses.

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
CN = "https://webadmin.windoent.com/front/op-public"
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


BASE_NUM = re.compile(r"^([A-Z]+\d*-\d{3})")


def base_number(raw):
    """CN card number -> (base number, is_alt). ('', False) if unparseable."""
    raw = (raw or "").strip()
    m = BASE_NUM.match(raw)
    if not m:
        return "", False
    return m.group(1), raw != m.group(1)


def cn_rows():
    """Every CN print row: {id, cardNumber, cardImg, cardOfferType}."""
    page, rows = 1, []
    while True:
        d = get(f"{CN}/cardList/cardlist/weblist?page={page}&limit=500")
        if d.get("code") != 0 or "page" not in d:
            raise RuntimeError(f"weblist page {page}: {str(d)[:200]}")
        d = d["page"]
        rows.extend(d["list"])
        if page >= d["totalPage"]:
            return rows
        page += 1
        time.sleep(DELAY)


def pick_cn_images(rows):
    """base number -> official CN scan URL, preferring the base art.

    A row shows the base art when its number has no variant suffix and its
    scan is not an _NN alt. Scans up to OP-16 are named <ms timestamp><number>
    (the number part can carry _NN even when the row's number does not);
    newer ones are UUIDs, so there the row's number decides. Among equals the
    lowest id (the earliest print) wins, which keeps rebakes stable.
    """
    imgs = {}
    for r in rows:
        num, alt = base_number(r.get("cardNumber"))
        url = (r.get("cardImg") or "").strip()
        if not num or not url:
            continue
        stem = url.rsplit("/", 1)[-1].split(".")[0]
        rank = (alt or bool(re.search(r"_\d+$", stem)), r["id"])
        if num not in imgs or rank < imgs[num][1]:
            imgs[num] = (url, rank)
    return {n: u for n, (u, _) in imgs.items()}


def main():
    packs = get(f"{PUNK}/packs.json")
    by_id = get(f"{PUNK}/index/cards_by_id.json")

    zh_path = OUT / "onepiece_zh.json"
    zh = json.loads(zh_path.read_text()) if zh_path.exists() else {}

    rows = cn_rows()
    print(f"CN print rows: {len(rows)}", flush=True)
    cn_imgs = pick_cn_images(rows)
    # base number -> id of the row to read its name from: the earliest plain
    # print, else the earliest alt art (same name). Some cards, such as most
    # of EB-04, only exist in CN as alt arts so far.
    rank = {}
    for r in rows:
        num, alt = base_number(r.get("cardNumber"))
        if num and (num not in rank or (alt, r["id"]) < rank[num]):
            rank[num] = (alt, r["id"])
    best = {n: rid for n, (_, rid) in rank.items()}

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
        # _pN = alternate art, _rN = reprint; both are versions of the base card
        m = re.match(r"^(.*?)(_[pr]\d+)?$", cid)
        base = m.group(1)
        if m.group(2):
            variants[base] = variants.get(base, 0) + 1
            continue
        pack = packs.get(str(c.get("pack_id")), {})
        label = (pack.get("title_parts") or {}).get("label") or ""
        # The official EN scans send Cross-Origin-Resource-Policy: same-site,
        # so browsers refuse to embed them cross-site. optcgapi mirrors them
        # per card number; the official CN scan is the baked fallback.
        cards[base] = {
            "i": base, "n": c.get("name") or "", "l": base,
            "s": label, "r": c.get("rarity") or "",
            "u": f"https://optcgapi.com/media/static/Card_Images/{base}.jpg",
        }
        if base in cn_imgs:
            cards[base]["c2"] = cn_imgs[base]
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
