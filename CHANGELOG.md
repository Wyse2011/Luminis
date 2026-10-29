# Changelog

## 2.0.3

**Fixes**
- Characters could glow solid white on other players' screens (especially with Lightless) when a glow
  layer was still syncing, or a material's glow layer slot pointed at the placeholder `dummy.tex`.
  Placeholder glow layers (under 32 pixels) now never glow.
- Fail-safe values: a Glow area, Glow mode or Debug view that this version doesn't know (from a newer
  Luminis) now means no glow / off. Before, it could light up the whole item or turn it black.
- The patcher now renames registers inside brackets, so epilogues that index a buffer at runtime read the
  right values.
- Builds no longer wait 1.1 seconds per shader (about 45 minutes saved on a full build).
- The build re-extracts vanilla shaders automatically when the game's shader package changed, and only
  picks date-named `vanilla` folders.
- Packaging refuses shader packages from an older build, so every part of a release matches.

**Note:** the white-glow fix runs on the viewer's side, so everyone should update to 2.0.3.

## 2.0

**New: gear, minions, mounts and weapons**
- Glow for `characterlegacy.shpk` and `character.shpk` (Gear and Gear (newer) parts), covering about
  97% of minions and mounts and practically all gear.
- Gear glow areas: Glow layer, Whole item, and Color table emissive (each color table row glows in its
  own Emissive Color; the game's own row glow switches off automatically).
- Luminis Rows: each of the 16 color table rows can be Animated, Static or Off.
- Light sensitivity on gear reads the game's light buffer directly.

**New animations and glow options**
- Pulse: like Blink, but between a minimum and maximum brightness (both layers).
- Hue cycle: every color rotates around the color wheel, so painted gradients flow.
- Eyes: Emissive mask glow area, for "glow editable" eye mods, using the game's own brightness curve.
- Animated colors now follow the color source's brightness instead of multiplying its hue, so brightly
  painted parts of any color take animation colors at full strength (no more parts fading out under
  Chroma).

**Tools**
- `luminis_game_extract.py`: extracts the vanilla shader packages straight from the game install, and
  surveys which shaders monsters, demihumans and gear use.
- `build_gear.py`: builds both gear packages.
- `luminis_settings.py` and `Luminis Settings.bat`: export and import Luminis settings between
  materials, with a small window.
- `mdl_merge.py`: merges two simple models onto one item, with validation.
- The build and packaging tools pick the newest `vanilla/<game version>/` folder automatically.
- `shpk_extract.py` and `shpk_patch.py` read shader tables entry by entry (needed for `character.shpk`).
- The splicer upgrades constant buffer declarations when an epilogue indexes them at runtime.

**Compatibility**
- Material settings grew from 15 to 19 Luminis registers (slots 26 to 44). Glow mods made for 1.x keep
  working; rebuild all shader packages when updating from source.
- Built for game version 2026.10.06 (eye, hair and skin shaders unchanged since 2026.09.15).

## 1.3
- Animation (blink, two-color, color steps, chroma, custom colors), a second glow layer per material,
  the natural glowing iris, and Layer 2 color source.

## 1.2 and earlier
- Glow for eyes, hair and skin: glow layers, light sensitivity, multi-color glow, per-material settings.
