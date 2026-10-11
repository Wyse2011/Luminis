# Luminis

Light-sensitive, multi-color glow for eyes, hair and skin in Final Fantasy XIV: Dawntrail.
Inspired by Atramentum Luminis (6.x), rebuilt from scratch for the 7.x shaders.

- **Glowing tattoos** from a painted glow layer: any colors, on any body mod (TBSE, Bibo, ...)
- **Glowing eyes**: painted masks, the eye's own colors, hue maps and rainbows
- **Glowing hair**: whole hair, highlights only, separate main and highlight colors, rainbows, or painted layers
- **Light sensitivity**: glow in darkness, in light, or always, tuned per material
- Works for every race, gender, face, body and hairstyle

## For players

1. Download the latest `Luminis_<version>_<game version>.pmp` from [Releases](../../releases).
2. Import it in Penumbra and enable it. On its own it changes nothing visible.
3. Install glow mods made for Luminis (glowing tattoos, eyes, hair).

**Load order** (Penumbra priority, highest last): body mod, tattoo mod, **Luminis**, glow mods.

After a game patch, disable Luminis until a release for the new game version is out.

## For creators

See the [Creator Guide](docs/creator-guide.md): painting glow layers, making glow mods with
`make_glow_mod.py`, eyes and hair, every setting, and troubleshooting.

## For developers

Building Luminis needs Windows, Python 3.11+, the Windows SDK (`fxc.exe`),
[3Dmigoto's cmd_Decompiler](https://github.com/bo3b/3Dmigoto/releases) in `tools/3dmigoto/`,
and Penumbra to export the vanilla shader packages. See the [Build Guide](docs/build-guide.md).

```
python tools/build_iris.py
python tools/build_hair.py
python tools/build_skin.py
python tools/package_luminis.py --version 1.0
```

This repository contains only the Luminis tools, shader code and documentation. It contains no
game files: the build reads your own game installation, and finished packages are published on the
Releases page.

## Credits and disclaimer

Created by Wyse. Inspired by Atramentum Luminis.

FINAL FANTASY XIV is a registered trademark of Square Enix. Luminis is a fan project, not affiliated
with or endorsed by Square Enix. Modding the game client is against its terms of service; use at
your own risk, and don't discuss mods in game.
