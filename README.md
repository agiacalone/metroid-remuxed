# Metroid Remuxed

A randomized Zebes every game, with a map that is drawn for each seed and fills in as you explore. Metroid Remuxed runs the **Metrandomizer** randomizer headless and adds the map from Metroid + Saving, as carried by Metroid Redux (see [mods/redux/README.md](mods/redux/README.md)).

It started as a command-line wrapper for **Metrandomizer** v07b, the NES Metroid randomizer by
Hex4F ([romhacking.net](https://www.romhacking.net/utilities/1437/)). Metrandomizer
builds a new Zebes for every seed: it rearranges the layout of Brinstar, Norfair,
Kraid's lair, Ridley's lair and part of Tourian, and shuffles every item. It is a
Windows GUI. This repo runs its generator headless on Linux, so seeds can be scripted.

**Requirements:** Linux with Docker, `unzip` and `curl`, and your own unmodified
*Metroid (USA)* ROM. Tested on Fedora 44 with Docker 29.

> [!IMPORTANT]
> This repo contains **none** of Metrandomizer. Download `Metrandomizer v07b.zip`
> yourself from romhacking.net, which blocks scripted downloads, and pass it to
> `metroid-rando setup`. Setup checks its SHA-256 and unpacks it into
> `~/.local/share/metrandomizer`. Nothing from it is committed (see `.gitignore`).

## How it works

`Metrandomizer.exe` is Python 3.7 code packed by PyInstaller, with a Tkinter
window on top. The generator itself is plain Python. So instead of running the
Windows program under Wine:

1. `setup` unpacks the bundled Python modules with
   [pyinstxtractor](https://github.com/extremecoders-re/pyinstxtractor), pinned to a
   commit and checked by SHA-256. It is GPL-3, so it is fetched at setup and never
   committed.
2. `gen` runs `driver/mrcli.py` in a `python:3.7` container with networking off.
   The driver fills in the app's own settings dictionary and calls the same
   routines its Randomize button does: `Game()` then `Game.randomize()`.

The same seed and settings always give the same ROM. That was checked by
generating seeds twice and comparing the files byte for byte.

| Piece | What it is |
|---|---|
| `bin/metroid-rando` | The command you run. Verifies and unpacks the app, maps paths into the container. |
| `driver/mrcli.py` | Sets the app's config, runs the generator, writes the ROM, the settings, a seed info file and three spoiler maps. |
| `presets/` | Five settings files, from one star to five. |
| `$MR_HOME` | `~/.local/share/metrandomizer`: the unpacked modules and the app's `data/` folder. |

## Commands

```sh
metroid-rando setup "Metrandomizer v07b.zip"   # once
metroid-rando options                          # every setting and its allowed values

export MR_ROM="/path/to/Metroid (USA).nes"
metroid-rando gen --preset 03-lost-expedition --out out
metroid-rando gen --settings out/4219082488/settings.json --seed 4219082488   # reproduce a seed

metroid-rando setup-redux                      # once, for --mod redux
metroid-rando gen --preset 01-return-to-zebes --mod redux   # Metroid Remuxed: with the map
```

| `gen` option | Meaning |
|---|---|
| `--preset NAME` | `presets/NAME.json` |
| `--settings FILE` | Any settings file, such as the `settings.json` beside an earlier seed |
| `--seed SEED` | A seed number. Omit for a random one. |
| `--out DIR` | Output directory, default `./out`. Each seed gets its own folder. |
| `--name NAME` | ROM file name, without `.nes` |
| `--rom FILE` | The base ROM. Or set `MR_ROM`. |
| `--mod redux[:no-fog]` | Metroid Remuxed: add the Metroid + Saving map, drawn for this seed, with fog of war unless `:no-fog`. Needs `setup-redux`, `git`, `cmake`, a C++ compiler and `python3`. |
| `-v` | Show each attempt |

Each seed folder holds the ROM, `settings.json`, `seedinfo.txt` (version, seed and
flag string) and `spoilers/` with three maps, least to most revealing:
`1-outline.svg`, `2-placeholders.svg` and `3-everything.svg`.

The ROM must be the unmodified **Metroid (USA)**, 131,088 bytes, SHA-1 of the
PRG/CHR data `FDBFC7871962F72A1EF57E5A7E456164FB93430B`.

## The presets

All five keep three quality-of-life fixes on: no pause when you collect an item,
the Ice Beam no longer cancels the Wave Beam, and A+B+Start+Select resets the game.

| Preset | Title | Difficulty | Map | Health | Pickups | Damage taken | Palettes |
|---|---|---|---|---|---|---|---|
| `01-return-to-zebes` | Return to Zebes | ★☆☆☆☆ | Very low complexity | 99 | ×10 | ×0.5 | Original |
| `02-colors-of-zebes` | Colors of Zebes | ★★☆☆☆ | Low | 99 | ×5 | ×1 | Random |
| `03-lost-expedition` | The Lost Expedition | ★★★☆☆ | Normal | 30 | ×2 | ×1 | Random |
| `04-hostile-planet` | Hostile Planet | ★★★★☆ | High | 30 | ×1 | ×2 | Random |
| `05-mother-brains-labyrinth` | Mother Brain's Labyrinth | ★★★★★ | Very high | 30 | ×0.5 | ×3 | Random |

Presets 3 to 5 also use the app's smaller status bar. "Random" palettes draw from
the app's 23 colour schemes. Edit a preset by editing its JSON; `metroid-rando options`
lists the allowed values.

## Gotchas

- **Some seeds cannot fit the map.** The generator raises "Bad seed! Not enough room
  to spawn Kraid's boss room" or "No space to put an elevator to Ridley". In the GUI
  you click Randomize again. Without `--seed`, the wrapper does the same and retries
  up to 20 times. A seed you chose yourself fails with that message.
- **The seed must be text inside the app.** Metrandomizer writes its log with
  `" seed " + seed`, so a numeric seed crashes it after the map is built. The driver
  passes it as a string.
- **Spoiler maps do not change the ROM.** The ROM is always built at the most
  detailed spoiler level, so the flag string on the title screen does not depend on
  the maps. The other two maps are redrawn from the same game afterwards.
- **No Samus sprite option.** The app has none. Themes come from map complexity,
  difficulty and palettes.

## Legal

The code in this repo is under the [MIT License](LICENSE). That covers the wrapper,
the driver and the presets, and nothing else.

*Metrandomizer* belongs to its author, Hex4F, and is distributed by romhacking.net.
No part of it, and no ROM, is included here. *Metroid* is a trademark of Nintendo.
This project is not affiliated with or endorsed by Nintendo or Hex4F.
