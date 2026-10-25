# Luminis

Light-sensitive, multi-color, animated glow for Final Fantasy XIV: Dawntrail, for eyes, hair, skin,
gear, minions and mounts. Inspired by Nylfae's Atramentum Luminis (6.x), rebuilt from scratch for the 7.x shaders.

- **Glowing tattoos** from painted glow layers: any colors, on any body mod (TBSE, Bibo+, ...)
- **Glowing eyes**: a natural glowing iris out of the box, painted designs, or the glow of "glow editable" eye mods
- **Glowing hair**: whole hair, highlights only, main color only, separate main and highlight colors, rainbows, or painted layers
- **Glowing gear, minions and mounts**: painted layers, the whole item, or each color table row in its own color
- **Per-row control on gear**: each color table row animated, steady or off
- **Two glow layers** per material, each with its own colors, light behavior and animation
- **Animation**: blink, pulse, two-color, rainbow color steps, chroma, custom colors, and hue cycle (painted gradients flow through the rainbow)
- **Light sensitivity**: glow in darkness, in light, or always, tuned per material
- Works for every race, gender, face, body and hairstyle

## For players

1. Download the latest `Luminis_<version>_<game version>.pmp` from [Releases](../../releases).
2. Import it in Penumbra and enable it. Under **Parts**, keep on what you use: Eyes, Hair, Skin, Gear, Gear (newer).
3. **Restart the game.** Shaders only load at startup, so restart after every install or update.
4. Install glow mods made for Luminis, or make your own (below). On its own, Luminis changes nothing visible.

**Load order** (Penumbra priority, highest last): body mod, tattoo mod, **Luminis**, glow mods.

After a game patch, disable Luminis until a release for the new game version is out.

## Making things glow

- **In Penumbra, no scripts:** the [Manual Guide](docs/Luminis-Manual-Guide.pdf) (PDF) walks through
  tattoos, eyes, hair, gear, animation and a second glow layer, with screenshots.
- **With the tools:** the [Creator Guide](docs/creator-guide.md) covers `make_glow_mod.py`, converting mods,
  moving settings between materials (`Luminis Settings.bat`), merging two models onto one item, every
  setting, and troubleshooting.

## For developers

Building Luminis needs Windows, Python 3.11+, the Windows SDK (`fxc.exe`), and
[3Dmigoto's cmd_Decompiler](https://github.com/bo3b/3Dmigoto/releases) in `tools/3dmigoto/`.
See the [Build Guide](docs/build-guide.md).

```
python tools/luminis_game_extract.py
python tools/build_iris.py
python tools/build_hair.py
python tools/build_skin.py
python tools/build_gear.py
python tools/package_luminis.py --version 2.0
```

This repository contains only the Luminis tools, shader code and documentation. It contains no game
files: the build reads your own game installation, and finished packages are published on the
Releases page.

## Credits and disclaimer

Created by Wyse. Inspired by Atramentum Luminis by Nylfae.

FINAL FANTASY XIV is a registered trademark of Square Enix. Luminis is a fan project, not affiliated
with or endorsed by Square Enix. Modding the game client is against its terms of service; use at
your own risk, and don't discuss mods in game.
