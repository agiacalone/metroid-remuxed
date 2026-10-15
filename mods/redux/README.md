# Metroid Remuxed: internals

Metroid Remuxed puts the map from [Metroid + Saving](https://www.romhacking.net/hacks/4471/) (snarfblam), as carried by [Metroid Redux](https://github.com/ShadowOne333/Metroid-Redux) (ShadowOne333, GPL-3), onto Metrandomizer seeds. Version 0.1 adds the map only.

```sh
python3 mods/redux/remux.py --redux REDUX_CHECKOUT --asar ASAR \
    "Metroid (USA).nes" SEED.nes OUT.nes
```

Check out Metroid Redux at `REDUX_COMMIT` and build Asar at `ASAR_COMMIT` (see `PINS`). Zelda Remuxed's `zelda-rando setup-redux` builds the same Asar.

## What you get

- A corner map in the HUD: the rooms around Samus, with a blinking blip.
- When paused, a 7x7-room window of the map. The D-pad scrolls it across Zebes.

The map shows all of Zebes from the start; it does not reveal rooms as you explore. It marks no items: only four fixed rooms carry a dot, including Kraid's and Ridley's. Metrandomizer moves items, not rooms or bosses, so the map is accurate on every seed.

## How it is built

Redux only patches the original ROM, so `remux.py` assembles Redux's own map source onto each seed:

1. **Expand.** The 128 KB seed becomes 256 KB of PRG. Banks 0-6 stay put, the fixed bank moves from bank 7 to bank 15, and banks 7-14 are new space. `ROMSwitch` stops merging the bank number into `$28` (`$C4F8`), as Redux does, so banks 8 and up can be selected.
2. **Assemble** Redux's `MapData.asm`, `Map_ROM.asm`, `Map_RAM.asm` and `MinimapPos.asm`. The map (1 KB) is in bank 14 at `$9400`. The code that runs from battery RAM is at `$9800`, copied to `$7D00-$7EFF`.
3. **Load.** Redux loads its map when a save file loads, and draws it with tiles from its CHR-ROM. A seed has no save files, and vanilla Metroid builds its graphics in CHR-RAM. So a loader (bank 14 `$9A00`) runs at the end of every graphics load (`LoadGFX`, `$C7D0`) through 13 bytes of glue at `$FFDB`. It does its work only when the map is missing from RAM: it copies the map and code to `$7900-$7EFF` and writes the map's sprite tiles.

Source edits, each required to match exactly once:

| File | Edit | Why |
|---|---|---|
| `MapData.asm` | include a remapped tilemap | empty cells used tile `$FE`, which is enemy graphics in vanilla; they use the free tile `$BE` |
| `Map_ROM.asm` | copy 6 pages, not 7; `rts` instead of jumping to bank 0 | stay inside the measured free RAM; return to the loader |
| `Map_RAM.asm` | the input handler ends with the seed's own pause check | see below |
| `Map_RAM.asm` | off-map cells use `$BE`, not `$FF` | `$FF` is enemy graphics in vanilla |
| `Map_RAM.asm` | drop `warnpc` | the pinned Asar has no `warnpc`; `main.asm` checks the end instead |
| `saving.asm` declarations | drop `Reset` | the pinned Asar rejects it as a name; the map code does not use it |

### Measured, not assumed

- **Sprite tiles.** No graphics group loads sprite tiles `$9A-$9F` or `$AA-$BF` (Metroid's table at `$C6E0`). `$A0-$A9` hold the HUD digits, and the map does not use them. The tiles come from Redux's `code/gfx/gfx03.bin`.
- **Battery RAM.** Vanilla and a seed both zero `$7900-$7AFF` and `$7B71-$7BFF` once at power-on, and never touch `$7900-$7EFF` in play or pause. The loader checks two map bytes in that range, so it reloads after any clear.
- **Fixed bank.** `$FFDB-$FFE8` is the only free run of 13 bytes or more that vanilla and all five test seeds leave alone.

## The safety check

`remux.py` refuses to write the ROM if any byte it changes in banks 0-6 or the fixed bank is one Metrandomizer changed. The only exception is the pause-mode button check at `$C9B1`. Vanilla checks Up+A on controller 2 there; Metrandomizer checks A+B+Select+Start on controller 1. Redux's map hook replaces those bytes with a jump to its input handler, so the build ends the handler with the seed's own check, read from the seed.

On the five 2026-10-14 seeds the build changes 36 bytes in the original banks and 1,859 in the new ones.

## Known limits

- **Sprite flicker near the HUD.** The minimap adds three sprites on each HUD row, which fills the NES's 8 sprites per line. With an enemy near the top of the screen, HUD letters can flicker. Vanilla Metroid flickers the same way under load.
- **Tested** in FCEUX on the five preset seeds: boot, play, doors, pause and map scrolling, in four different start areas. Not yet played on hardware.
