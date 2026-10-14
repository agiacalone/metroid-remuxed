"""mrcli: run Metrandomizer's own generator without its GUI.

Runs inside the python:3.7 container (Metrandomizer v07b was built with
Python 3.7 and its bytecode only loads there). The modules are the ones
PyInstaller bundled into Metrandomizer.exe, extracted by `metroid-rando setup`.
This file only sets the app's config dictionary and calls the same routines
its Randomize button does: Game() then Game.randomize().

    python mrcli.py MODULES SETTINGS.json ROM SEED OUTDIR NAME

Writes OUTDIR/NAME.nes, settings.json, seedinfo.txt and spoilers/*.svg.
"""
import json
import os
import shutil
import sys

# Spoiler map levels, least to most revealing, and the file each becomes.
SPOILER_LEVELS = [("Basic Outline", "1-outline.svg"),
                  ("Powerup Placeholders", "2-placeholders.svg"),
                  ("Everything", "3-everything.svg")]


def main(modules, settings_path, rom, seed, outdir, name):
    sys.path[:0] = [d for d in (os.path.join(modules, x) for x in os.listdir(modules))
                    if d.endswith("_extracted") and os.path.isdir(d)] + [modules]
    import Metrandomizer as M

    settings = json.load(open(settings_path))
    unknown = set(settings) - set(M.configBits)
    if unknown:
        sys.exit(f"mrcli: unknown settings: {', '.join(sorted(unknown))}")

    os.makedirs(outdir, exist_ok=True)
    os.chdir(outdir)
    # The app reads its patches and spoiler icons from ./data, relative to the cwd.
    if not os.path.exists("data"):
        os.symlink(os.path.join(modules, "data"), "data")

    M.config.update(M.getDefaultConfig())
    M.config.update(settings)
    M.config["Original ROM"] = rom
    M.config["Random Seed"] = str(seed)           # the log concatenates it as text
    M.config["Destination"] = f"{name}.nes"
    # The ROM is always built at the most detailed spoiler level, so the flag
    # string on the title screen is the same whatever maps are requested.
    M.config["Spoiler Map"] = "Everything"
    flags = M.getFlagString()

    try:
        game = M.Game()
        game.randomize()
    except M.Randomizerror as e:
        # Some seeds cannot fit the map (no room for Kraid or Ridley). The GUI
        # just asks for another click; the wrapper retries with a new seed.
        print(f"mrcli: bad seed {seed}: {e}", file=sys.stderr)
        sys.exit(3)

    # Redraw the map at each level from the same game; this happens after the
    # ROM is saved, so it cannot change the ROM.
    os.makedirs("spoilers", exist_ok=True)
    for level, fname in SPOILER_LEVELS:
        M.config["Spoiler Map"] = level
        game.generateMapSpoiler()
        shutil.move("Map.svg", os.path.join("spoilers", fname))

    M.config["Spoiler Map"] = "Everything"
    saved = {k: M.config[k] for k in M.configBits}
    json.dump(saved, open("settings.json", "w"), indent=2)
    with open("seedinfo.txt", "w") as f:
        f.write(f"Version: {M.version}\nSeed: {seed}\nFlags: {flags}\n")
    for leftover in ("Log.txt", "data"):
        if os.path.islink(leftover):
            os.unlink(leftover)
        elif os.path.exists(leftover):
            os.remove(leftover)
    print(f"seed {seed} flags {flags} -> {os.path.join(outdir, name)}.nes")


if __name__ == "__main__":
    if len(sys.argv) != 7:
        sys.exit(__doc__.strip().splitlines()[-3])
    main(*sys.argv[1:])
