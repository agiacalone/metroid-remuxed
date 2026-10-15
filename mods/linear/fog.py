#!/usr/bin/env python3
"""fog.py - add fog of war to the map of a Metroid + Saving based hack, such as
"Metroid - Linear".

    fog.py --asar PATH [--session-fog] HACK.nes OUT.nes

HACK.nes must carry the map code of Metroid + Saving 0.5.2, as Metroid Redux
does: the copy routine at bank 14 $9000, the code that runs from battery RAM
at $9800 (copied to $7D00), MinimapPos at $7EA8. Every patch site is checked
against those bytes first; anything else is refused.

What it adds:
  - A room shows on the map once Samus has been in it, an elevator connector
    once she has stood next to it. The visited mark is bit 6 of the cell's
    byte in the RAM map; every map tile ($9A-$BF) leaves it clear.
  - Per save file (default): each mark is also written to that file's bitmap
    in battery RAM ($7600, $7680, $7700; 128 bytes, one bit per cell). Loading
    a file (LoadGame, bank 0 $AADD) applies its bitmap; starting on an empty
    file clears it. Exploration is kept even when Samus dies without saving.
  - --session-fog: marks live in the RAM map only and reset when a file loads.

Free space used: RAM code $9A56-$9AFF (copied to $7F56-$7FFF; no code
addresses it), bank 14 ROM after the copy routine ($9030-), the bitmaps at
$7600-$777F and the file-load code at $7780-$77FF, copied there at every
reset (no code addresses $7568-$77FF except the file menu's $758E and $75AE).
"""
import argparse
import pathlib
import subprocess
import sys
import tempfile

HEADER = 0x10
BANK = 0x4000

# (bank, address, expected bytes, what)
SITES = [
    (15, 0xCB57, "20 A8 7E", "HUD hook: jsr MinimapPos ($7EA8)"),
    (14, 0x99A8, "20 D4 7D CE 01 7D", "MinimapPos: jsr GetMapCords / dec MinimapY"),
    (14, 0x98C6, "B1 04 A6 03 A4 06 60", "GetMapTile: lda ($04),y / ldx $03 / ldy $06 / rts"),
    (14, 0x9000, "A9 00 85 00 A9 94 85 01 A9 00 85 02 A9 79 85 03 A2 07", "MapLoadEntryPoint: copy 7 pages $9400 -> $7900"),
    (14, 0x9022, "A0 00 4C EF C4", "MapLoadEntryPoint tail: ldy #0 / jmp ROMSwitch"),
    (0, 0xAADD, "AE 75 68 BD 00 75 D0 03", "LoadGame: ldx SaveFileIndex / lda File_InUse,x / bne"),
]
FREE = [(14, 0x9030, 0x9400), (14, 0x9A56, 0x9B00)]   # must be all $00 in the hack
PATCHED = [(14, 0x99A8, 3), (14, 0x98C6, 4), (14, 0x9022, 5), (0, 0xAADD, 3)]

SOURCE = r"""
norom
!headersize = $10
macro org(address, bank)
	org <address>-$8000+$4000*<bank>+!headersize
	base <address>
endmacro

MinimapX = $7D00
MinimapY = $7D01
GetMapCords = $7DD4
ROMSwitch = $C4EF
SaveFileIndex = $6875
SaveFileNum = $6876
File_InUse = $7500
MapRAM = $7900
BLANK = $FE

; --- RAM code, copied to $7F56-$7FFF with the rest of the map code ---
%org($9A56,14)
base $7F56

; MinimapPos used to start with jsr GetMapCords; mark Samus's cell as well.
MarkGlue:
	jsr GetMapCords
	lda MinimapX
	sta $06
	lda MinimapY
	sta $07
	jsr MarkCell
	inc $07			; an elevator connector below
	jsr ElevCheck
	dec $07			; or above
	dec $07
	jsr ElevCheck
	rts

ElevCheck:			; mark ($06,$07) if it holds an elevator tile
	jsr CellPtr
	bcs .r
	ldy #$00
	lda ($00),y
	and #$BF
	cmp #$B9
	beq MarkCell
	cmp #$BA
	beq MarkCell
.r:
	rts

MarkCell:			; mark cell ($06,$07) visited
	jsr CellPtr
	bcs .r
	ldy #$00
	lda ($00),y
	ora #$40
	sta ($00),y
if !persist
	lda $06			; bitmap byte: Y*4 + X/8, in this file's 128 bytes
	lsr
	lsr
	lsr
	sta $02
	lda $07
	asl
	asl
	ora $02
	sta $02
	ora FogBase		; this file's bitmap ($7600, $7680 or $7700)
	sta $02
	lda FogBase+1
	sta $03
	lda $06
	and #$07
	tax
	lda BitTab,x
	ora ($02),y
	sta ($02),y
endif
.r:
	rts

CellPtr:			; $00/$01 = MapRAM + Y*32 + X; carry set if off the map
	lda $06
	cmp #$20
	bcs .r
	lda $07
	cmp #$20
	bcs .r
	lsr
	lsr
	lsr
	clc
	adc.b #MapRAM>>8
	sta $01
	lda $07
	asl
	asl
	asl
	asl
	asl
	ora $06
	sta $00
	clc
.r:
	rts

; GetMapTile's read: unvisited cells show blank; visited ones lose the mark.
FogRead:
	lda ($04),y
	and #$40
	beq +
	lda ($04),y
	and #$BF
	ldx $03
	rts
+	lda #BLANK
	ldx $03
	rts

BitTab:
	db $01,$02,$04,$08,$10,$20,$40,$80
FogBase:			; set by ApplyFog when a file loads
	db $00,$76
MapFogEnd:
base off
assert MapFogEnd <= $8000, "fog RAM code runs past $7FFF"

; --- Hooks ---
%org($99A8,14)			; MinimapPos (RAM $7EA8): jsr GetMapCords
	jsr MarkGlue
%org($98C6,14)			; GetMapTile (RAM $7DC6): lda ($04),y / ldx $03
	jsr FogRead
	nop
%org($9022,14)			; end of MapLoadEntryPoint: ldy #0 / jmp ROMSwitch
	jmp ApplyFog
	nop
	nop

; --- Bank 14 ROM, after the copy routine. Runs at every reset, after the map
; is copied to RAM (Metroid + Saving does not copy it when a file loads; a
; save ends in a soft reset). Copies FileFog to $7780 for LoadGame to call.
%org($9030,14)
ApplyFog:
if !persist
	ldy #$7F
-	lda FileFogROM,y
	sta FileFog,y
	dey
	bpl -
endif
	ldy #$00
	jmp ROMSwitch

if !persist
FileFogROM:
base $7780
; LoadGame (bank 0) starts with ldx SaveFileIndex; it now calls this first.
; SaveFileNum and SaveFileIndex were just set from the chosen slot, and the
; map in RAM is fresh from the last reset.
FileFog:
	lda SaveFileNum		; this file's bitmap: $7600, $7680 or $7700
	and #$01
	beq +
	lda #$80
+	sta $00
	sta FogBase
	lda SaveFileNum
	lsr
	clc
	adc #$76
	sta $01
	sta FogBase+1
	ldx SaveFileIndex
	lda File_InUse,x
	bne .apply
	ldy #$7F		; empty slot: a new game starts unexplored
	lda #$00
-	sta ($00),y
	dey
	bpl -
	bmi .done
.apply:
	lda.b #MapRAM		; $02/$03 walks the map 8 cells per bitmap byte
	sta $02
	lda.b #MapRAM>>8
	sta $03
	ldy #$00
.byte:
	sty $05
	lda ($00),y
	sta $04
	ldy #$00
.bit:
	lsr $04
	bcc +
	lda ($02),y
	ora #$40
	sta ($02),y
+	iny
	cpy #$08
	bne .bit
	lda $02
	clc
	adc #$08
	sta $02
	bcc +
	inc $03
+	ldy $05
	iny
	bpl .byte
.done:
	ldx SaveFileIndex	; LoadGame's first instruction
	rts
FileFogEnd:
base off
assert FileFogEnd <= $7800, "FileFog runs past $77FF"
assert FileFogROM+(FileFogEnd-FileFog) <= $9400, "load code runs into the map at $9400"

%org($AADD,0)			; LoadGame: ldx SaveFileIndex
	jsr FileFog
endif
"""


class FogError(Exception):
    pass


def off(bank, addr):
    return HEADER + bank * BANK + addr - (0xC000 if bank == 15 else 0x8000)


def check_sites(rom):
    if len(rom) != HEADER + 16 * BANK + 16 * 0x2000 or rom[4] != 16:
        raise FogError("not an expanded Metroid + Saving ROM (256 KB PRG, 128 KB CHR)")
    for bank, addr, want, what in SITES:
        want = bytes.fromhex(want)
        got = rom[off(bank, addr):off(bank, addr) + len(want)]
        if got != want:
            raise FogError(f"bank {bank} ${addr:04X} ({what}): expected {want.hex(' ')}, found {got.hex(' ')}")
    for bank, lo, hi in FREE:
        if any(rom[off(bank, lo):off(bank, hi)]):
            raise FogError(f"bank {bank} ${lo:04X}-${hi - 1:04X} is not free")


def check_result(rom, built):
    allowed = set()
    for bank, lo, hi in FREE:
        allowed.update(range(off(bank, lo), off(bank, hi)))
    for bank, addr, n in PATCHED:
        allowed.update(range(off(bank, addr), off(bank, addr) + n))
    bad = [i for i in range(len(rom)) if rom[i] != built[i] and i not in allowed]
    if bad:
        raise FogError(f"changed {len(bad)} byte(s) outside the hooks and free space, first at file offset {bad[0]:#x}")
    return sum(1 for i in range(len(rom)) if rom[i] != built[i])


def build(asar, hack_path, out_path, persist=True):
    rom = pathlib.Path(hack_path).read_bytes()
    check_sites(rom)
    with tempfile.TemporaryDirectory(prefix="mfog-") as tmp:
        work = pathlib.Path(tmp)
        (work / "fog.asm").write_text(f"!persist = {1 if persist else 0}\n" + SOURCE)
        (work / "out.nes").write_bytes(rom)
        r = subprocess.run([asar, "--no-title-check", "--fix-checksum=off", "fog.asm", "out.nes"],
                           cwd=work, capture_output=True, text=True)
        if r.returncode != 0:
            raise FogError("asar failed:\n" + (r.stdout + r.stderr).strip())
        built = (work / "out.nes").read_bytes()
    n = check_result(rom, built)
    pathlib.Path(out_path).write_bytes(built)
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--asar", required=True, help="Asar binary")
    ap.add_argument("--session-fog", action="store_true",
                    help="keep the explored map in RAM only; it resets when a file loads")
    ap.add_argument("hack")
    ap.add_argument("out")
    a = ap.parse_args()
    try:
        n = build(a.asar, a.hack, a.out, persist=not a.session_fog)
    except FogError as e:
        sys.exit(f"fog: {e}")
    print(f"{pathlib.Path(a.out).name}: fog of war added ({'per save file' if not a.session_fog else 'per session'}); {n} bytes changed")


if __name__ == "__main__":
    main()
