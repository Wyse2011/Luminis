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

- **Material parameters:** fifteen float4 settings added to the material buffer (slots 26 to 40).
- **Texture bindings:** every patched shader gets two new material texture slots, `g_SamplerLuminis`
  and `g_SamplerLuminis2` (glow layers 1 and 2); eyes also get the eye color texture
  (`g_SamplerDiffuse`, for the hue map). The slots are declared as material textures, so Penumbra's
  material editor shows them as `dummy.tex` rows and glow mods can be made by hand.
- **The clock:** animation reads the game's `m_LoopTime` from `g_PbrParameterCommon` (c0.x), which every
  eye, hair and skin composite shader already binds.
- **Eyes** also capture the eye mask's blue channel, the game's iris marker, for the natural iris glow.

Shaders to patch are found automatically by the resources they bind, so every race, gender, face,
body and hairstyle is covered: currently 16 eye, 160 hair and 128 skin shaders.

| Parameter | Slot | Contents |
| --- | --- | --- |
| `g_LuminisColor` | 26 | tint R, G, B, intensity |
| `g_LuminisLight` | 27 | dark start, dark end, mode, sensitivity |
| `g_LuminisMisc` | 28 | color source, area mix, glow area, debug view |
| `g_LuminisDetail` | 29 | detail, detail gain, rainbow length, rainbow shift |
| `g_LuminisHighlight` | 30 | highlight tint R, G, B, separate highlight (hair) |
| `g_LuminisAnim` | 31 | animation mode, speed, steps, softness |
| `g_LuminisAnimColor` | 32 | color 2 R, G, B |
| `g_LuminisAnimColor3` | 33 | color 3 R, G, B |
| `g_LuminisAnimColor4` | 34 | color 4 R, G, B |
| `g_LuminisL2Color` | 35 | layer 2 tint R, G, B, intensity |
| `g_LuminisL2Light` | 36 | layer 2 dark start, dark end, mode, sensitivity |
| `g_LuminisL2Anim` | 37 | layer 2 animation mode, speed, steps, softness |
| `g_LuminisL2AnimColor` | 38 | layer 2 color 2 R, G, B, layer 2 color source |
| `g_LuminisL2AnimColor3` | 39 | layer 2 color 3 R, G, B |
| `g_LuminisL2AnimColor4` | 40 | layer 2 color 4 R, G, B |

Animation modes: 0 off, 1 blink, 2 two-color, 3 color steps, 4 chroma, 5 custom colors. Eye glow areas:
0 natural iris, 1 glow layer, 2 painted eye mask, 3 whole eye. Skin glow areas: 0 glow layer, 1 whole
skin. Hair glow areas: 0 whole hair, 1 highlights, 2 main color, 3 glow layer.

Shader-package defaults keep intensity at 0, so materials without Luminis settings never glow.

## Requirements

- Windows, Python 3.11+ (`pip install pillow` for `make_glow_mod.py`)
- Windows SDK, with `fxc.exe` on the PATH
- [3Dmigoto's cmd_Decompiler](https://github.com/bo3b/3Dmigoto/releases) extracted to `tools/3dmigoto/`
  (the `cmd_Decompiler-<version>.zip`, not the main 3Dmigoto package)
- Penumbra, for testing (the vanilla shader packages come straight from your game install)

## Folder layout

```
luminis/
  tools/        Python tools (this repository)
  include/      luminis_glow.hlsli, the glow code (this repository)
  devkit/       Penumbra dev-kit files: iris, hair, skin, characterlegacy, character .json (this repository)
  docs/         guides (this repository)
  vanilla/<game version>/   vanilla shader packages and shader_survey.json (not committed)
  blobs/, compiled/         build intermediates                        (not committed)
  release/                  packaged .pmp files                        (not committed)
```

## First-time setup

1. Create a Penumbra mod called **Luminis Dev** in your Penumbra mod folder (the tools assume
   `D:\SquareEnix\Luminis Dev`; change `MOD` near the top of the tools if yours differs).
2. Extract the vanilla shader packages straight from your game install (read-only):
   `python tools/luminis_game_extract.py` (add `--game "<FFXIV folder>\game"` if it isn't in the default
   location). This writes every relevant shader package into `vanilla/<game version>/`, plus a survey of
   which shaders monsters, demihumans and gear use. The build and packaging tools pick the newest
   `vanilla/` folder automatically, so there's no version to edit anywhere.

## Building

```
python tools/build_iris.py
python tools/build_hair.py
python tools/build_skin.py
python tools/build_gear.py      (characterlegacy + character: about 1,700 shaders, an hour or more)
```

To test a change on a few shaders first: `python tools/build_luminis.py characterlegacy 3 53 63`.

Each build extracts the vanilla shaders (first run only), patches every composite shader, adds the
material parameters and texture bindings, and writes the result into the Luminis Dev mod. Progress is
shown per shader; hair and skin take several minutes. Shaders that don't fit are reported as `SKIP`
and stay vanilla.

The first time, register the shaders and dev-kits in the mod:

```
python tools/mod_place.py file "D:\SquareEnix\Luminis Dev\shader\sm5\shpk\iris.shpk" shader/sm5/shpk/iris.shpk
python tools/mod_place.py file devkit\iris.json penumbra/shpk_devkit/iris.json
```

(and the same for `hair`, `skin`, `characterlegacy` and `character`). Then click **Reload Mod** in Penumbra and **restart the game**:
shader packages only load at startup.

## Packaging a release

```
python tools/clean_dev_mod.py --apply      (optional: strips test files from Luminis Dev into archive/)
python tools/package_luminis.py --version 2.0
```

This writes `release/Luminis_<version>_<game version>.pmp`, with a **Parts** option group (Eyes, Hair,
Skin, Gear, Gear (newer)); the gear parts are included when built. It refuses to package a shader that doesn't carry the Luminis parameters. Publish the `.pmp` as a
GitHub Release asset.

## Patch day

After any game patch, assume Luminis is broken until checked.

1. Post a notice for users to disable Luminis until an update is out.
2. Run `python tools/luminis_game_extract.py --no-survey`; it creates `vanilla/<new game version>/`.
3. Compare each package with the previous version (`fc /b vanilla\<old>\iris.shpk vanilla\<new>\iris.shpk`).
   Unchanged packages need nothing.
4. Rebuild the changed ones (`build_gear.py` covers both gear packages). The build notices the changed
   vanilla package and re-extracts its shaders automatically. Review any `SKIP` or `FAIL` lines: a changed shader structure may need an
   adjustment in `luminis_asm.py`. Check that each build declares `g_SamplerLuminis` and
   `g_SamplerLuminis2`, and that the eye build adds 48 bindings (three per shader).
5. Restart the game, test eyes, hair and a glow mod, then package and publish.

## Tools

| Tool | Purpose |
| --- | --- |
| `build_iris.py`, `build_hair.py`, `build_skin.py`, `build_gear.py` | Build shader packages (shortcuts for `build_luminis.py`) |
| `luminis_game_extract.py` | Extract vanilla shader packages from the game install; survey shader use |
| `build_luminis.py` | The build pipeline: discover, patch, extend, write into the mod |
| `luminis_asm.py` | Assembly patching with the iris, hair, skin and gear epilogues |
| `shpk_extract.py` | Export every shader from a `.shpk`, numbered like Penumbra |
| `shpk_patch.py` | Replace shader blobs in a `.shpk` |
| `shpk_add_params.py` | Add the Luminis material parameters |
| `shpk_add_texture.py` | Add texture bindings, or declare a new material texture slot |
| `package_luminis.py` | Build the release `.pmp` |
| `clean_dev_mod.py` | Strip Luminis Dev to the production files (moves the rest to `archive/`) |
| `mtrl_luminis.py` | Add or change Luminis settings in a material; attach a glow layer |
| `make_glow_mod.py` | Create a glow mod from one or two PNG glow layers (eyes, hair, skin) |
| `make_preset_mod.py` | Create a glow mod from a material and settings, without a glow layer |
| `luminis_convert_mod.py` | Make a Luminis copy of any Penumbra mod |
| `luminis_vanilla.py`, `sqpack.py` | Generate Luminis materials for every vanilla eye and hair |
| `mod_place.py` | Put files into a mod at their game paths and register them |
| `luminis_settings.py`, `Luminis Settings.bat` | Export and import Luminis settings between materials (window or command line) |
| `mdl_merge.py` | Merge two simple models onto one item |
| `magenta_batch.py`, `color_test.py` | Diagnostics: find which shader variant draws something |

## Troubleshooting builds

| Symptom | Cause | Fix |
| --- | --- | --- |
| `compilation failed` for every shader | `include/luminis_glow.hlsli` and `luminis_asm.py` are from different versions | Update both together |
| `SKIP ... expected one final color multiply` | The shader's structure differs from the known patterns | Inspect its disassembly; adjust `luminis_asm.py` |
| Game crashes at startup after a build | A malformed shader | Restore the vanilla `.shpk` in Luminis Dev, rebuild, check for errors |
| Changes don't show in-game | Shader packages load only at startup | Restart the game |
| `SKIP ... epilogue uses arrays` for every shader | The epilogue compiled to an indexed array (runtime indexing) | Select values with comparisons instead of runtime indexes in the stub |
| Penumbra won't save edited shader packages | Penumbra's editor limitation | Use the tools (`shpk_patch.py` and friends) instead |
