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

**Fog of war** (default): a room shows on the map once Samus has been in it, and an elevator connector once she has stood next to it. Use `--no-fog` to show the whole world from the start. The explored map lasts until power-off, deaths included; vanilla Metroid has no save files to keep it in. The map marks no items.

## The map is drawn for each seed

Metrandomizer generates a new world for every seed: seed 01 changes 597 of the 1,024 cells of the world map (bank 0 `$A53E`). Redux's map is a hand-drawn picture of vanilla Zebes, so `tools/zebes.py` draws each seed's world with Redux's tiles instead:

1. **Walk the world as the game scrolls it.** Each area grows from its start cell (`$95D7` in its bank). In a horizontal stretch, Samus scrolls left and right until a door; in a vertical shaft, up and down. Passing a door switches direction, except at the door pairs marked in the special-object table (type 9). Elevators end their area's shaft.
2. **Read doors from the room data**, after each room's objects: entries of type 2, `$Ax` on the right and `$Bx` on the left. A door can be recorded in either of the two rooms.
3. **Drop filler rooms.** The grid puts a room past many shaft ends so the scroll engine has something to load. A shaft dead end with no doors and nothing in it is dropped.
4. **Pick each cell's tile** from how it scrolls and where its doors are: shaft top, middle or bottom; corridor end or middle; or a single room. Each comes in no-door, left, right and both-door versions. Elevators get the dotted tile between the two areas.

Cells with an item or elevator also seed the walk, so no such room is left off the map.

**Checked against vanilla:** the generated vanilla map has the same corridors, shafts and junctions as Redux's hand-drawn one, and 70% of tiles are identical. Most differences are deliberate. Redux draws some chains of door-separated rooms (Norfair) as one corridor, while the generator draws the doors, as the game has them.

## How it is built

Redux only patches the original ROM, so `remux.py` assembles Redux's own map source onto each seed:

1. **Expand.** The 128 KB seed becomes 256 KB of PRG. Banks 0-6 stay put, the fixed bank moves from bank 7 to bank 15, and banks 7-14 are new space. `ROMSwitch` stops merging the bank number into `$28` (`$C4F8`), as Redux does, so banks 8 and up can be selected.
2. **Assemble** Redux's `MapData.asm`, `Map_ROM.asm`, `Map_RAM.asm` and `MinimapPos.asm`. The map (1 KB) is in bank 14 at `$9400`. The code that runs from battery RAM is at `$9800`, copied to `$7D00-$7FFF`.
3. **Load.** Redux loads its map when a save file loads, and draws it with tiles from its CHR-ROM. A seed has no save files, and vanilla Metroid builds its graphics in CHR-RAM. So a loader (bank 14 `$9B00`) runs at the end of every graphics load (`LoadGFX`, `$C7D0`) through 13 bytes of glue at `$FFDB`. It does its work only when the map is missing from RAM: it copies the map and code to `$7900-$7FFF` and writes the map's sprite tiles.

Source edits, each required to match exactly once:

| File | Edit | Why |
|---|---|---|
| `MapData.asm` | include the generated tilemap | the seed's own world; empty cells use the free tile `$BE`, because Redux's `$FE` is enemy graphics in vanilla |
| `Map_ROM.asm` | `rts` instead of jumping to bank 0 | return to the loader |
| `Map_RAM.asm` | the input handler ends with the seed's own pause check | see below |
| `Map_RAM.asm` | off-map cells use `$BE`, not `$FF` | `$FF` is enemy graphics in vanilla |
| `MinimapPos.asm` | replaced: reads each cell through `GetMapTile` | Redux's corner map has no edge check, so in column 0 or row 0 it read nine cells from the wrong row. Vanilla Zebes never uses the edges; generated worlds do |
| `Map_RAM.asm` | drop `warnpc` | the pinned Asar has no `warnpc`; `main.asm` checks the end instead |
| `saving.asm` declarations | drop `Reset` | the pinned Asar rejects it as a name; the map code does not use it |

### Measured, not assumed

- **Sprite tiles.** No graphics group loads sprite tiles `$9A-$9F` or `$AA-$BF` (Metroid's table at `$C6E0`). `$A0-$A9` hold the HUD digits, and the map does not use them. The tiles come from Redux's `code/gfx/gfx03.bin`.
- **Battery RAM.** Vanilla and a seed both zero `$7900-$7AFF` and `$7B71-$7BFF` once at power-on, and never touch `$7900-$7FFF` in play or pause. No instruction in either addresses `$7F00-$7FFF`. The loader checks two map bytes in that range, so it reloads after any clear.
- **Fixed bank.** `$FFDB-$FFE8` is the only free run of 13 bytes or more that vanilla and all five test seeds leave alone.

## Fog of war

The visited mark is bit 6 of each cell's byte in the RAM map: every map tile (`$9A-$BF`) has it clear. `MarkVisited`, called from the corner map every frame in play, sets it on Samus's cell and on an elevator connector directly above or below. `GetMapTile` returns the blank tile for an unmarked cell, so the corner and pause maps both hide unexplored rooms. The loader's check masks the bit, or a visit to one of its two check cells would look like a cleared map and reload it.

The fog code needs Redux's seventh page of RAM code (`$7F00-$7FFF`), which the measurements show is unused by vanilla and the seeds. The loader therefore sits at bank 14 `$9B00`, after the seven pages it copies.

## The safety check

`remux.py` refuses to write the ROM if any byte it changes in banks 0-6 or the fixed bank is one Metrandomizer changed. The only exception is the pause-mode button check at `$C9B1`. Vanilla checks Up+A on controller 2 there; Metrandomizer checks A+B+Select+Start on controller 1. Redux's map hook replaces those bytes with a jump to its input handler, so the build ends the handler with the seed's own check, read from the seed.

On the five 2026-10-14 seeds the build changes 36 bytes in the original banks and 1,859 in the new ones.

## Known limits

- **Shafts can be drawn a cell or two too tall.** Where the grid continues past a ceiling that Samus cannot pass, the generator cannot tell without reading each room's collision data. No room is hidden by this.
- **No landmark dots.** Redux marks Kraid's and Ridley's rooms with a dot; the generated map does not mark bosses.
- **Sprite flicker near the HUD.** The minimap adds three sprites on each HUD row, which fills the NES's 8 sprites per line. With an enemy near the top of the screen, HUD letters can flicker. Vanilla Metroid flickers the same way under load.
- **Tested** in FCEUX on the five preset seeds: boot, play, doors, pause and map scrolling, in four start areas; in 700 samples the minimap never centred on an empty cell. Played on a Steam Deck (RetroDECK, FCEUmm) on seed 01: the corner map at a map edge, through doors, after an elevator ride into another area, the pause map and its scrolling, and Metrandomizer's A+B+Select+Start reset.
