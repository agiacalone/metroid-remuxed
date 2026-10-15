# Troubleshooting

Each entry gives the symptom, a check that confirms the cause, and the fix.

> [!CAUTION]
> Use the unmodified *Metroid (USA)* ROM. The wrapper rejects any other version or an
> already-patched ROM by checksum.

## Setup

| Symptom | Confirm | Fix |
|---|---|---|
| `not set up; run: metroid-rando setup` | `cat ~/.local/share/metrandomizer/vendor/VERSION`; want `v07b` | Run `metroid-rando setup` with the zip. |
| `... is not Metrandomizer v07b.zip (SHA-256 mismatch)` | `sha256sum "Metrandomizer v07b.zip"`; want `ca29f36c…` | The download was cut short, or it is another version. Download v07b again. |
| `permission denied` on the Docker socket | `docker info` | Add yourself to the `docker` group, or run rootless Docker. |

## Generating

| Symptom | Confirm | Fix |
|---|---|---|
| `... is not an unmodified Metroid (USA)` | `tail -c +17 rom.nes \| sha1sum`; want `fdbfc787…` | Use the unmodified USA ROM. |
| `no usable seed in 20 attempts` | Rerun with `-v`; each attempt shows "Bad seed!" | Rare at normal settings. Very High map complexity fails more often; run it again. |
| `generation failed` with a seed you chose | The log names "Bad seed!" | That seed cannot fit its map at these settings. Pick another seed. |

## Remuxed (`--mod redux`)

| Symptom | Confirm | Fix |
|---|---|---|
| `Metroid Redux is not set up; run: metroid-rando setup-redux` | `ls ~/.local/share/metrandomizer/asar/asar ~/.local/share/metrandomizer/redux` | Run `metroid-rando setup-redux`. |
| `Asar source checksum mismatch` | `grep ASAR_SHA256 mods/redux/PINS` | The download was cut short, or GitHub changed the archive. Retry; if it persists, rebuild Asar from the pinned commit and update `ASAR_SHA256`. |
| `source edit matched 0 times` or `matched 2 times` | `git -C ~/.local/share/metrandomizer/redux log -1 --format=%h`; want the `REDUX_COMMIT` in `PINS` | Redux's source differs from the pin. Run `setup-redux` again. |
| `would overwrite N byte(s) Metrandomizer changed` | The message lists the addresses | A seed changed code the map hooks into. Open an issue with the seed and settings. |
| A tall column of blue squares at the right of the screen | You resumed a save state after replacing the ROM | The state brought back the previous build's map code. Use the emulator's **Restart**. |
| The corner map shows rooms Samus is not in | Pause: does the pause map agree with the room you see? | Make sure the ROM came from `--mod redux` of this repo at or after `7e108d6`; earlier builds used the original game's map. |
| The map is empty after relaunching the emulator | Was the game resumed from a save state? | Without a state, Metroid starts fresh: the explored map lasts until power-off. Use save states to keep it. |
