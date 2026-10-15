# Documentation

| Guide | For | Time |
|---|---|---|
| [Getting started](getting-started.md) | Your first seed with the map, from a fresh Linux machine | 20 minutes |
| [Troubleshooting](troubleshooting.md) | An error message, a seed that will not generate, or a map that looks wrong | 5 minutes per entry |
| [Main README](../README.md) | Commands, options, presets, the map and design notes | Reference |
| [Remuxed internals](../mods/redux/README.md) | How the map is drawn, every edit to Redux, the RAM map, the safety checks | Reference |

> [!CAUTION]
> Two rules hold everywhere in this repo:
>
> - **Use the unmodified *Metroid (USA)* ROM.** The wrapper rejects anything else by checksum.
> - **Never commit files from the randomizer or Metroid Redux.** Neither may be redistributed here. Setup keeps both in `~/.local/share/metrandomizer`, and `.gitignore` keeps the app's files and ROMs out; keep it that way.
