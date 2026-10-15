# Getting started

From nothing to a randomized Metroid ROM with a map, on Linux. About 20 minutes, most of it
building Asar and pulling the Python image.

## The pieces

```mermaid
flowchart LR
    R["Your USA ROM"] --> G["Metrandomizer<br/>(its own Python, in a container)"]
    G -- "a new world" --> S["Seed ROM"]
    S --> M["Remuxed:<br/>this seed's map, drawn and<br/>assembled onto the seed"]
    M --> O["Your game"]
```

1. **Metrandomizer** makes the seed: a new layout for Zebes and a new place for every item.
   It is a Windows program, but its generator is Python, so it runs in a small container
   with no network.
2. **Remuxed** then adds the map to that seed: a corner map in the HUD and a map on the pause
   screen, drawn from the seed's own world, with fog of war. This step is optional
   (`--mod redux`).

## What you need

| Need | Why |
|---|---|
| Docker | The generator runs in a `python:3.7` container, the only Python its bytecode loads in |
| `unzip`, `curl` | To unpack the app and fetch sources (`sudo dnf install unzip curl`) |
| `git`, `cmake`, a C++ compiler, Python 3 | For Remuxed: to fetch Metroid Redux and build the Asar assembler (`sudo dnf install git cmake gcc-c++ python3`) |
| `Metrandomizer v07b.zip` | Downloaded by hand from [romhacking.net](https://www.romhacking.net/utilities/1437/), which blocks scripted downloads |
| An unmodified **Metroid (USA)** ROM | The randomizer patches it. Other versions and hacks are rejected. |

> [!NOTE]
> **Two common misconceptions.** First, that this repo *is* the randomizer: it holds only the
> wrapper, and you download the randomizer yourself. Second, that Metroid Redux's map can be
> patched onto a seed: it cannot, because Redux's map is a picture of the original Zebes and
> every seed has a different one. Remuxed draws each seed's map from its own world instead,
> which is why it needs its own setup step.

## 1. Set up the randomizer

```sh
git clone https://github.com/agiacalone/metroid-remuxed.git
cd metroid-remuxed
./bin/metroid-rando setup ~/Downloads/"Metrandomizer v07b.zip"
```

Setup checks the zip's SHA-256, extracts the Python modules bundled in `Metrandomizer.exe`,
and keeps them in `~/.local/share/metrandomizer/vendor`.

Good result: the last line reads `metroid-rando: Metrandomizer v07b unpacked to /home/you/.local/share/metrandomizer/vendor`.

## 2. Set up Remuxed

```sh
./bin/metroid-rando setup-redux
```

This clones Metroid Redux at the commit pinned in `mods/redux/PINS`, downloads the Asar
source, checks its SHA-256, and builds it. It takes a minute or two.

Good result: `metroid-rando: Metroid Redux dd40ab7 and Asar b8c2623 ready in /home/you/.local/share/metrandomizer`.

## 3. Make a seed

```sh
export MR_ROM="$HOME/roms/Metroid (USA).nes"
./bin/metroid-rando gen --preset 01-return-to-zebes --mod redux --out out
```

Leave out `--mod redux` for a plain Metrandomizer seed. Use `--mod redux:no-fog` to see the
whole map from the start. With `--mod redux`, a line reports how many bytes Remuxed wrote; any
safety failure stops the build with the address and the reason.

The output folder `out/<SEED>/` holds:

| File | What it is |
|---|---|
| `metroid-SEED.nes` | The game. 256 KB with the map. Use `--name` to choose the file name. |
| `settings.json` | The exact settings. Give it and the seed number to someone else to reproduce the game. |
| `seedinfo.txt` | Version, seed and flag string. The flags also show on the title screen. |
| `spoilers/` | Three maps of the seed, from an outline to everything. Leave them closed unless stuck. |

## 4. Play

Any NES emulator with MMC1 works. Tested with FCEUmm in RetroArch (Steam Deck, ROCKNIX
handhelds) and with FCEUX. In game:

- The **corner map** shows the rooms around Samus. A room appears once you have been in it.
- **Pause** to see a larger map; the **D-pad** scrolls it.
- **A+B+Select+Start** resets the game.
- Metroid has no save files: the explored map lasts until power-off. An emulator save state
  keeps it.

> [!TIP]
> After you replace a Remuxed ROM with a newer build, choose the emulator's **Restart** once
> instead of resuming a save state. A state made with the old build brings back its old map
> code.

## If something goes wrong

See [troubleshooting.md](troubleshooting.md). Each entry has a check that confirms the cause.
