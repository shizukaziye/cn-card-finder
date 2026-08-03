# CN Card Finder

Find a Pokémon, One Piece or Riftbound card in English, confirm it by its
picture, and get the Chinese name plus ready-made search strings for sourcing
the simplified-Chinese print from China (集换社 / jihuanshe, Taobao, Superbuy).

**Live: https://shizukaziye.github.io/cn-card-finder/**

## Why

jihuanshe is app-only and mainland-only, and Chinese listings use Chinese card
names. This tool bridges the gap: search in English, copy the Chinese string,
paste it into the jihuanshe app or an agent's Taobao search. The in-app guide
covers the buying routes (agent custom order, Taobao/Xianyu through an agent,
or CN export shops).

## Data

Baked JSON under `data/` — the page calls no third-party API at run time
except the image CDNs.

| Game | English index | Chinese names |
|------|---------------|---------------|
| Pokémon | TCGdex via the weekly [michi-binder](https://github.com/shizukaziye/michi-binder) bake (TCG Pocket sets dropped) | Derived: PokeAPI official zh-Hans species names + prefix/suffix rules + hand-checked trainer staples |
| One Piece | see `scripts/build_onepiece.py` | Same card numbers in every language; CN names where a source exists |
| Riftbound | see `scripts/build_riftbound.py` | Same card numbers; champion names from Riot ddragon zh_CN |

Rebuild everything:

```bash
python3 scripts/build_pokemon.py
python3 scripts/build_pokemon_zh.py
```

A GitHub Action reruns the bakes weekly and commits changes.

## Running locally

```bash
python3 -m http.server 8741
```

Plain HTML + JS, no build step. Card images load from the source CDNs and are
© their respective owners; this is an unofficial fan tool with nothing for
sale.
