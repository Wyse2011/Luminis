# Luminis Build Guide

How Luminis is built, packaged and updated after game patches. For making glow mods, see the
[Creator Guide](creator-guide.md).

## How it works

Luminis replaces three shader packages: `iris.shpk` (eyes), `hair.shpk` and `skin.shpk`. Every
**composite** pixel shader in each package (the shaders that produce a surface's final color) gets a
small piece of extra code, the **epilogue**, spliced in just before the final color is written. The
epilogue adds glow from a mask and a color source, scaled by how dark it is around the surface.

Most of the game's shaders can't be decompiled reliably, so Luminis patches their **assembly**:

1. `luminis_asm.py` disassembles each vanilla shader with 3Dmigoto's `cmd_Decompiler`.
2. It compiles the epilogue (`include/luminis_glow.hlsli` plus profile-specific setup) with `fxc`,
   matched to that shader's registers, and splices the instructions in before the final color multiply.
3. It reassembles the shader with the original input/output signatures.

The build also extends each package:

- **Material parameters:** five float4 settings added to the material buffer (slots 26 to 30).
- **Texture bindings:** each patched shader gets one extra texture. Eyes read the eye color texture
  (`g_SamplerDiffuse`, for the hue map); hair reads `g_SamplerDecal` (its glow layer); skin gets a new
  material texture slot, `g_SamplerLuminis` (its glow layer), declared in the package.

Shaders to patch are found automatically by the resources they bind, so every race, gender, face,
body and hairstyle is covered: currently 16 eye, 160 hair and 128 skin shaders.

| Parameter | Slot | Contents |
| --- | --- | --- |
| `g_LuminisColor` | 26 | tint R, G, B, intensity |
| `g_LuminisLight` | 27 | dark start, dark end, mode, sensitivity |
| `g_LuminisMisc` | 28 | color source, area mix, glow area, debug view |
| `g_LuminisDetail` | 29 | detail, detail gain, rainbow length, rainbow shift |
| `g_LuminisHighlight` | 30 | highlight tint R, G, B, separate highlight (hair) |

Shader-package defaults keep intensity at 0, so materials without Luminis settings never glow.

## Requirements

- Windows, Python 3.11+ (`pip install pillow` for `make_glow_mod.py`)
- Windows SDK, with `fxc.exe` on the PATH
- [3Dmigoto's cmd_Decompiler](https://github.com/bo3b/3Dmigoto/releases) extracted to `tools/3dmigoto/`
  (the `cmd_Decompiler-<version>.zip`, not the main 3Dmigoto package)
- Penumbra, to export vanilla shader packages and test

## Folder layout

```
luminis/
  tools/        Python tools (this repository)
  include/      luminis_glow.hlsli, the glow code (this repository)
  devkit/       Penumbra dev-kit files: iris.json, hair.json, skin.json (this repository)
  docs/         guides (this repository)
  vanilla/<game version>/   vanilla iris.shpk, hair.shpk, skin.shpk   (not committed)
  blobs/, compiled/         build intermediates                        (not committed)
  release/                  packaged .pmp files                        (not committed)
```

## First-time setup

1. Create a Penumbra mod called **Luminis Dev** in your Penumbra mod folder (the tools assume
   `D:\SquareEnix\Luminis Dev`; change `MOD` near the top of the tools if yours differs).
2. Export the vanilla shader packages: in Penumbra's **On-Screen** tab, expand any eye, hair and skin
   material, and use the save icon on each **Shader Package** row (check it shows no mod name). Save
   them as `vanilla/<game version>/iris.shpk`, `hair.shpk` and `skin.shpk`.
3. Check that the game version folder name matches `vanilla / "2026.09.15"` in `build_luminis.py` and
   `GAME_VERSION` in `package_luminis.py`.

## Building

```
python tools/build_iris.py
python tools/build_hair.py
python tools/build_skin.py
```

Each build extracts the vanilla shaders (first run only), patches every composite shader, adds the
material parameters and texture bindings, and writes the result into the Luminis Dev mod. Progress is
shown per shader; hair and skin take several minutes. Shaders that don't fit are reported as `SKIP`
and stay vanilla.

The first time, register the shaders and dev-kits in the mod:

```
python tools/mod_place.py file "D:\SquareEnix\Luminis Dev\shader\sm5\shpk\iris.shpk" shader/sm5/shpk/iris.shpk
python tools/mod_place.py file devkit\iris.json penumbra/shpk_devkit/iris.json
```

(and the same for `hair` and `skin`). Then click **Reload Mod** in Penumbra and **restart the game**:
shader packages only load at startup.

## Packaging a release

```
python tools/clean_dev_mod.py --apply      (optional: strips test files from Luminis Dev into archive/)
python tools/package_luminis.py --version 1.0
```

This writes `release/Luminis_<version>_<game version>.pmp`, with a **Parts** option group (Eyes, Hair,
Skin). It refuses to package a shader that doesn't carry the Luminis parameters. Publish the `.pmp` as a
GitHub Release asset.

## Patch day

After any game patch, assume Luminis is broken until checked.

1. Post a notice for users to disable Luminis until an update is out.
2. Export the new vanilla `iris.shpk`, `hair.shpk` and `skin.shpk` into `vanilla/<new game version>/`.
3. Update the game version in `build_luminis.py` and `package_luminis.py`, and delete the old
   `blobs/iris`, `blobs/hair` and `blobs/skin` folders so they're re-extracted.
4. Rebuild all three. Review any `SKIP` or `FAIL` lines: a changed shader structure may need an
   adjustment in `luminis_asm.py`.
5. Restart the game, test eyes, hair and a glow mod, then package and publish.

## Tools

| Tool | Purpose |
| --- | --- |
| `build_iris.py`, `build_hair.py`, `build_skin.py` | Build one shader package (shortcuts for `build_luminis.py`) |
| `build_luminis.py` | The build pipeline: discover, patch, extend, write into the mod |
| `luminis_asm.py` | Assembly patching with the iris, hair and skin epilogues |
| `shpk_extract.py` | Export every shader from a `.shpk`, numbered like Penumbra |
| `shpk_patch.py` | Replace shader blobs in a `.shpk` |
| `shpk_add_params.py` | Add the Luminis material parameters |
| `shpk_add_texture.py` | Add texture bindings, or declare a new material texture slot |
| `package_luminis.py` | Build the release `.pmp` |
| `clean_dev_mod.py` | Strip Luminis Dev to the production files (moves the rest to `archive/`) |
| `mtrl_luminis.py` | Add or change Luminis settings in a material; attach a glow layer |
| `make_glow_mod.py` | Create a glow mod from a PNG glow layer |
| `luminis_convert_mod.py` | Make a Luminis copy of any Penumbra mod |
| `luminis_vanilla.py`, `sqpack.py` | Generate Luminis materials for every vanilla eye and hair |
| `mod_place.py` | Put files into a mod at their game paths and register them |
| `magenta_batch.py`, `color_test.py` | Diagnostics: find which shader variant draws something |

## Troubleshooting builds

| Symptom | Cause | Fix |
| --- | --- | --- |
| `compilation failed` for every shader | `include/luminis_glow.hlsli` and `luminis_asm.py` are from different versions | Update both together |
| `SKIP ... expected one final color multiply` | The shader's structure differs from the known patterns | Inspect its disassembly; adjust `luminis_asm.py` |
| Game crashes at startup after a build | A malformed shader | Restore the vanilla `.shpk` in Luminis Dev, rebuild, check for errors |
| Changes don't show in-game | Shader packages load only at startup | Restart the game |
| Penumbra won't save edited shader packages | Penumbra's editor limitation | Use the tools (`shpk_patch.py` and friends) instead |
