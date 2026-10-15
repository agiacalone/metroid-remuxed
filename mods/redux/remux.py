#!/usr/bin/env python3
"""remux.py - put Metroid + Saving's map, as carried by Metroid Redux, onto a
Metrandomizer seed.

Metroid Redux only patches the original ROM, so it cannot go onto a seed as a
patch. This assembles Redux's own map source onto the seed instead, with a few
source edits and a small loader, and checks every byte it writes.

    remux.py --redux DIR --asar PATH ORIGINAL SEED OUT

ORIGINAL is an unmodified Metroid (USA) ROM, SEED a Metrandomizer seed made
from it. DIR is a Metroid Redux checkout (see PINS); PATH an Asar binary.

What the build does:
  1. Expands the seed from 128 KB to 256 KB of PRG. Banks 0-6 stay put, the
     fixed bank moves from bank 7 to bank 15, and banks 7-14 are new space.
  2. Draws this seed's map with Redux's tiles (tools/zebes.py): Metrandomizer
     generates a new world, so Redux's hand-drawn vanilla map would be wrong.
     Assembles Redux's MapData.asm, Map_ROM.asm, Map_RAM.asm and MinimapPos.asm,
     with the map in bank 14 and the code that runs from battery RAM at
     $7D00-$7EFF.
  3. Adds a loader. Vanilla Metroid builds its graphics in CHR-RAM, one area at
     a time, so the map's sprite tiles ($9A-$9F, $AA-$BF: no area loads those)
     are written by the loader, not by a CHR-ROM bank as in Redux. The loader
     runs at the end of every graphics load and does its work only when the map
     is missing from RAM, which is after power-on and after the game clears
     that RAM.
  4. Refuses to write the ROM if any byte it changes is one Metrandomizer
     changed, except the pause-mode button check, which is kept inside the
     map's input handler (see ALLOWED_OVERWRITES).
"""
import argparse
import hashlib
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "tools"))
import zebes  # noqa: E402

HEADER = 0x10
BANK = 0x4000
# SHA-1 of the PRG+CHR data (after the header) of Metroid (USA).
ROM_SHA1 = "fdbfc7871962f72a1ef57e5a7e456164fb93430b"
MAP_FILES = ["MapData.asm", "Map_ROM.asm", "Map_RAM.asm", "MinimapPos.asm"]
BLANK = 0xBE        # free tile in the map's range: empty and off-map cells
CHECKS = (0x000, 0x280)   # tilemap offsets the loader checks to see if the map is in RAM


class RemuxError(Exception):
    pass


def edit(text, edits, name):
    """Apply source edits. Each pattern must match exactly once."""
    for pattern, repl in edits:
        n = len(re.findall(pattern, text, flags=re.S))
        if n != 1:
            raise RemuxError(f"{name}: source edit matched {n} times (needs 1): {pattern[:60]}")
        text = re.sub(pattern, lambda _m: repl, text, count=1, flags=re.S)
    return text


def fixed(rom, addr, expanded):
    """File offset of a fixed-bank address."""
    return HEADER + (15 if expanded else 7) * BANK + addr - 0xC000


def expand(seed):
    if len(seed) != HEADER + 8 * BANK or seed[:4] != b"NES\x1a" or seed[4] != 8 or seed[5] != 0:
        raise RemuxError("the seed is not an unexpanded 128 KB Metroid ROM with CHR-RAM")
    out = bytearray(seed[:HEADER])
    out[4] = 16
    out += seed[HEADER:HEADER + 7 * BANK]
    out += b"\xff" * (8 * BANK)
    out += seed[HEADER + 7 * BANK:]
    return out


def pause_check(seed):
    """The seed's pause-mode button check at $C9B1: lda <zp> / and #<mask>.
    Vanilla has lda $15 / and #$88 (Up+A on controller 2); Metrandomizer has
    lda $14 / and #$F0 (A+B+Select+Start on controller 1). The map's input
    handler takes over these four bytes, so it must end with the same check."""
    b = seed[fixed(seed, 0xC9B1, False):][:4]
    if b[0] != 0xA5 or b[2] != 0x29:
        raise RemuxError(f"unexpected pause check at $C9B1: {b.hex(' ')}")
    return b[1], b[3]


def build_sources(work, redux, seed):
    src = pathlib.Path(redux) / "code"
    saving = (src / "gameplay/saving.asm").read_text()
    m = re.search(r"; Existing vars.*?\nMapData\s*=[^\n]*\n", saving, flags=re.S)
    if not m:
        raise RemuxError("saving.asm: declarations block not found")
    # Newer Asar rejects "Reset" as a name; the map code does not use it.
    decls = edit(m.group(0), [(r"\nReset\s*=[^\n]*", "")], "saving.asm declarations")
    shutil.copy(src / "macros.asm", work / "macros.asm")
    for f in MAP_FILES:
        shutil.copy(src / "gameplay/saving" / f, work / f)

    # Metrandomizer generates a new world, so Redux's hand-drawn map of vanilla
    # Zebes (MapTilemap.bin) would be wrong. Draw this seed's world with the
    # same tiles instead (tools/zebes.py).
    tilemap = zebes.tilemap(seed)
    if BLANK in set(tilemap):
        raise RemuxError("the generated map uses the blank tile; check the tile choice")
    # Empty cells: Redux's tile $FE is enemy graphics in vanilla. Use a free
    # tile in the map's own range instead.
    tilemap = bytearray(BLANK if t == zebes.EMPTY else t for t in tilemap)
    (work / "MapTilemap-remux.bin").write_bytes(tilemap)

    gfx = (src / "gfx/gfx03.bin").read_bytes()
    tile = lambda t: gfx[t * 16:t * 16 + 16]
    (work / "tiles-9a.bin").write_bytes(b"".join(tile(t) for t in range(0x9A, 0xA0)))
    (work / "tiles-aa.bin").write_bytes(b"".join(tile(0xFE) if t == BLANK else tile(t) for t in range(0xAA, 0xC0)))

    zp, mask = pause_check(seed)
    (work / "MapData.asm").write_text(edit((work / "MapData.asm").read_text(), [
        (r'incbin "MapTilemap\.bin"', 'incbin "MapTilemap-remux.bin"'),
    ], "MapData.asm"))
    (work / "Map_ROM.asm").write_text(edit((work / "Map_ROM.asm").read_text(), [
        # Copy six pages ($7900-$7EFF, the measured free range), not Redux's seven.
        (r"ldx #\$07", "ldx #$06"),
        # Return to the loader instead of jumping to bank 0's file code.
        (r"ldy #\$00\s*\n\s*jmp ROMSwitch", "rts"),
    ], "Map_ROM.asm"))
    (work / "Map_RAM.asm").write_text(edit((work / "Map_RAM.asm").read_text(), [
        # The four bytes the pause hook replaces, as the seed has them.
        (r"lda Joy1Status[^\n]*\n\s*and #\$88", f"lda ${zp:02X}\n\tand #${mask:02X}"),
        # Off-map cells: Redux's tile $FF is enemy graphics in vanilla.
        (r"lda #\$FF\s*\n\s*rts", f"lda #${BLANK:02X}\n\trts"),
        # Newer Asar has no warnpc; the end of this code is checked in main.asm.
        (r"\nwarnpc \$9A56", ""),
    ], "Map_RAM.asm"))

    glue = f"""
; Loader, bank 14. Called with bank 14 mapped, from MapGlue.
%org($9A00,14)
MapLoad:
	lda MapRAM+${CHECKS[0]:03X}
	cmp #${tilemap[CHECKS[0]]:02X}
	bne .load
	lda MapRAM+${CHECKS[1]:03X}
	cmp #${tilemap[CHECKS[1]]:02X}
	beq .done
.load:
	jsr MapLoadEntryPoint	; map and RAM code -> $7900-$7EFF
	bit $2002
	lda #$09		; sprite tiles $9A-$9F
	sta $2006
	lda #$A0
	sta $2006
	ldx #$00
-	lda MapTilesA,x
	sta $2007
	inx
	cpx #$60
	bne -
	lda #$0A		; sprite tiles $AA-$BF ($A0-$A9 are the HUD digits)
	sta $2006
	lda #$A0
	sta $2006
	ldx #$00
-	lda MapTilesB,x
	sta $2007
	inx
	bne -
-	lda MapTilesB+$100,x
	sta $2007
	inx
	cpx #$60
	bne -
.done:
	rts
MapTilesA:
	incbin "tiles-9a.bin"
MapTilesB:
	incbin "tiles-aa.bin"
assert pc() <= $A000, "loader runs past $9FFF"

; Fixed bank: free bytes before the "METROID" string at $FFE9.
%org($FFDB,15)
MapGlue:
	ldy #$0E
	jsr ROMSwitch
	jsr MapLoad
	ldy $23			; the bank the graphics loader returns to
	jmp ROMSwitch
assert pc() <= $FFE9, "glue runs into the METROID string"

; End of the graphics loader (LoadGFX): was ldy $23 / jmp ROMSwitch.
%org($C7D0,15)
	jmp MapGlue

; ROMSwitch: stop merging the bank number into $28, so banks 8-15 work.
; Metroid Redux makes the same change (mother.asm).
%org($C4F8,15)
	nop
	nop
"""
    (work / "glue.asm").write_text(glue)
    (work / "main.asm").write_text("\n".join([
        "norom", "!headersize = $10", "optimize dp always", "dpbase 0",
        'incsrc "macros.asm"',
        decls,
        'incsrc "MapData.asm"',
        'incsrc "Map_ROM.asm"',
        "%org($9800,14)",
        "base $7D00",
        "\tdb $00,$00,$00,$00",
        'incsrc "Map_RAM.asm"',
        'incsrc "MinimapPos.asm"',
        "MapRamEnd:",
        "base off",
        'assert MapRamEnd <= $7F00, "map RAM code runs past $7EFF"',
        'incsrc "glue.asm"',
        "",
    ]))
    return tilemap


# Bytes the build may change although Metrandomizer changed them too.
ALLOWED_OVERWRITES = {
    # $C9B1-$C9B4: the pause-mode button check (lda/and), replaced by
    # jsr MapInputHandler / nop. The handler ends with the seed's own check.
    0xC9B2: "pause check (kept in MapInputHandler)",
    0xC9B4: "pause check (kept in MapInputHandler)",
}


def check(original, seed, built):
    """Every changed byte in the original banks must be one the seed left as
    vanilla, or an allowed overwrite. Returns (changed bytes, new-bank bytes)."""
    exp = expand(seed)
    bad = []
    changed = 0
    for bank in list(range(7)) + [15]:
        src_bank = 7 if bank == 15 else bank
        for i in range(BANK):
            off = HEADER + bank * BANK + i
            if built[off] == exp[off]:
                continue
            changed += 1
            o = HEADER + src_bank * BANK + i
            addr = (0xC000 if bank == 15 else 0x8000) + i
            if seed[o] != original[o] and not (bank == 15 and addr in ALLOWED_OVERWRITES):
                bad.append(f"bank {src_bank} ${addr:04X}")
    if bad:
        raise RemuxError(f"would overwrite {len(bad)} byte(s) Metrandomizer changed: {', '.join(bad[:8])}")
    new = sum(1 for o in range(HEADER + 7 * BANK, HEADER + 15 * BANK) if built[o] != 0xFF)
    return changed, new


def remux(redux, asar, original_path, seed_path, out_path):
    original = pathlib.Path(original_path).read_bytes()
    if hashlib.sha1(original[HEADER:]).hexdigest() != ROM_SHA1:
        raise RemuxError("ORIGINAL is not an unmodified Metroid (USA) ROM")
    seed = pathlib.Path(seed_path).read_bytes()
    with tempfile.TemporaryDirectory(prefix="mremux-") as tmp:
        work = pathlib.Path(tmp)
        build_sources(work, redux, seed)
        rom = work / "out.nes"
        rom.write_bytes(expand(seed))
        r = subprocess.run([asar, "--no-title-check", "--fix-checksum=off", "main.asm", "out.nes"],
                           cwd=work, capture_output=True, text=True)
        if r.returncode != 0:
            raise RemuxError("asar failed:\n" + (r.stdout + r.stderr).strip())
        built = rom.read_bytes()
    changed, new = check(original, seed, built)
    pathlib.Path(out_path).write_bytes(built)
    return changed, new


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--redux", required=True, help="Metroid Redux checkout")
    ap.add_argument("--asar", required=True, help="Asar binary")
    ap.add_argument("original")
    ap.add_argument("seed")
    ap.add_argument("out")
    a = ap.parse_args()
    try:
        changed, new = remux(a.redux, a.asar, a.original, a.seed, a.out)
    except RemuxError as e:
        sys.exit(f"remux: {e}")
    print(f"{pathlib.Path(a.out).name}: map added; {changed} bytes changed in the original banks, {new} in the new ones")


if __name__ == "__main__":
    main()
