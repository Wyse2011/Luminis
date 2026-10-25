# Luminis Creator Guide

## What Luminis is

Luminis adds light-sensitive, multi-color and animated glow to eyes, hair, skin, gear, minions and mounts in Dawntrail. It's the spiritual successor to Nylfae's Atramentum Luminis, rebuilt from scratch for the 7.x shaders. Glow can come from the surface itself (a natural glowing iris, glowing hair) or from up to **two painted glow layers**, each with its own colors, light behavior and animation (blinking, pulsing, color cycling, chroma, hue cycling).

It works in three layers, each a separate Penumbra mod:

| Layer | What it contains | Who makes it |
| --- | --- | --- |
| **Luminis** (the framework) | Replacement eye, hair, skin and gear shaders, plus the dev-kit files that add the Luminis Glow controls to Penumbra | Installed once by every user |
| **Tattoo or body mod** | The normal look: TBSE or Bibo, tattoos painted into the color texture | Body and tattoo artists, as today |
| **Glow mod** | A Luminis copy of the material plus a glow layer texture that says what glows, and in which colors | You, with `make_glow_mod.py` |

On its own, the framework changes nothing you can see. A material glows only when it has Luminis settings with an intensity above 0, and that's exactly what glow mods provide. Because the glow lives in its own mod, users can switch it on and off without touching the tattoo.

**Load order (Penumbra priority, highest last):**

1. Body mod (TBSE, Bibo, ...)
2. Tattoo mod
3. Luminis
4. Glow mods

Glow mods must sit above the body mod, because they replace its material. Luminis must sit above anything else that replaces `iris.shpk`, `hair.shpk`, `skin.shpk`, `characterlegacy.shpk` or `character.shpk`.

**Prefer working entirely in Penumbra, without scripts?** The [Manual Guide](Luminis-Manual-Guide.pdf) (PDF) walks through everything in-game, with screenshots. This guide covers the tools.

**What you need to make glow mods:** Penumbra, an image editor that exports PNG with transparency (Photoshop, GIMP, Krita, Paint.NET), and the Luminis tools with Python (`pip install pillow` once, for reading PNGs).

## Quick start: a glowing tattoo

1. **Find the body material.** In Penumbra's **On-Screen** tab, expand your character's body and find the skin material your tattoo sits on (for TBSE Viera male, that's `mt_c1701b0001_b.mtrl`). Note its game path from the left column, and export it with the save icon.
2. **Paint the glow layer.** In Photoshop, paint only the glowing parts of your tattoo, in the colors you want them to glow, on an otherwise transparent canvas the same size as the body texture. Export as PNG. (Details in the next section.)
3. **Make the glow mod:**

```
python tools\make_glow_mod.py --name "My Tattoo - Glow" --layer my_glow.png --material mt_c1701b0001_b.mtrl chara/human/c1701/obj/body/b0001/material/v0001/mt_c1701b0001_b.mtrl
```

4. **Enable it.** In Penumbra: **Settings > Rediscover Mods**, enable the new mod, give it a higher priority than your body and tattoo mods, and restart the game.
5. **Tune it.** Open the material in the glow mod's **Advanced Editing > Materials** tab. The **Luminis Glow** section controls brightness, when it glows, and more.

By default, the glow appears in darkness and fades out in bright light. Add `--mode always` to the command while testing, so you can see it anywhere.

## Painting a glow layer

A glow layer is an image where **only the glowing parts are painted** and everything else is **transparent**. Its colors become the glow colors, and its opacity decides how strongly each pixel glows. Any colors work, including white and pastels, and one layer can hold as many colors as you like.

**Set up the canvas**

1. In Penumbra's **Textures** tab, load the body's color texture (for TBSE, the `_d` texture of the material you're using) and **Export as TGA** or PNG. This is only a layout reference.
2. Open it in Photoshop. The canvas size must match the body texture (usually 2048×2048 or 4096×4096), so tattoo and glow line up exactly.
3. Add a **new layer** above it for the glow. If you have the tattoo itself, place it in between as a second reference.

**Paint**

- Paint the glow on the new layer, in full color, wherever the tattoo should light up. Leave everything else empty.
- **Opacity is glow strength.** Fully opaque pixels glow at full intensity; semi-transparent ones glow less. A soft brush gives soft glow edges.
- **Glow doesn't have to follow the tattoo.** You can outline it, light up only certain lines, or add glow where there's no ink at all.
- **Keep shapes bold.** From a normal camera distance, the game shows small, blurred versions of textures, so thin lines blur together. Fine detail shows up close, for example in GPose.

**Export**

Hide every layer except the glow, so it sits on transparency with no background, then **Export as PNG** with transparency on. The PNG goes straight into `make_glow_mod.py`.

If the skin looks lighter overall once the glow is on, a reference or background layer was probably still partly visible when you exported. Check with the **Debug view: Glow mask** setting: everything outside your painting should be pure black.

## Making a glow mod

`make_glow_mod.py` turns a glow layer into a ready-to-use Penumbra mod. It converts the image to a game texture, makes a Luminis copy of each material you give it with the glow layer attached, and writes the mod folder with all redirections.

```
python tools\make_glow_mod.py --name "NAME" --layer GLOW.png --material MATERIAL.mtrl GAME/PATH/OF/MATERIAL.mtrl [options]
```

| Option | What it does | Default |
| --- | --- | --- |
| `--name` | Name of the new mod | (required) |
| `--layer` | The glow layer: PNG, TGA or a converted `.tex` | (required) |
| `--material FILE GAME_PATH` | A material to make glow, with its game path. Repeat it for several materials that share the layer. Works for skin, hair and eye materials | (required) |
| `--intensity` | Glow brightness | 1.5 |
| `--mode` | `dark` (glow in darkness), `always`, or `light` (glow in light) | dark |
| `--tint R,G,B` | Multiplies the layer's colors; `1,1,1` keeps them as painted | 1,1,1 |
| `--area-mix` | 0 = react to light hitting the surface, 1 = to the area's overall brightness | 0.5 |
| `--layer-path` | Where the glow texture goes in-game | Next to the material's textures |
| `--layer2` | A second glow layer with its own settings (see Glow layer 2) | none |
| `--layer2-intensity` | Layer 2 brightness | 1.5 |
| `--layer2-mode` | Layer 2's light behavior: `dark`, `always` or `light` | always |
| `--layer2-tint R,G,B` | Multiplies layer 2's colors | 1,1,1 |
| `--layer2-anim MODE,SPEED,STEPS,SOFTNESS` | Layer 2's animation, for example `4,0.2,4,1` for a slow chroma | 0,1,4,1 (off) |
| `--update` | Replace the glow in an existing glow mod of the same name | off |

**Finding the right material**

Body mods often split the body across several materials, and the tattoo has to be on the one that covers it. In the **On-Screen** tab, expand the body model: each **Skin Textures** entry is a material. TBSE, for example, draws most of the body with the `_b` material, while `_a` only covers a small seam. Use the material from the **body mod your users run**, exported with the On-Screen save icon. Its game path is the left column of the same row.

**Release builds:** a PNG becomes an uncompressed texture (about 20 MB at 2048×2048). For releases, convert the PNG to **BC7** in Penumbra's Textures tab first (set the output dropdown to BC7, then **Save as TEX**) and pass the `.tex` to `--layer`. It's about a quarter of the size and looks the same.

**Changing the glow later:** tweak it live in Penumbra's material editor and click **Save to File**, or rerun the command with `--update` and new options.

## Sharing glow mods

A glow mod is a normal Penumbra mod, so you share it the usual way: select it in Penumbra's Mods tab, open **Edit Mod**, and click **Export Mod** to get a `.pmp`. Fill in its name, author, version and description there first.

There are two common ways to release a glowing tattoo:

- **Separate tattoo and glow mods.** Users install your tattoo mod as usual, plus the glow mod on top, and toggle the glow mod on or off. This is the easiest to make and the easiest to maintain.
- **One mod with a glow option.** Copy the tattoo's files into the glow mod (or the glow files into the tattoo mod) and put the glow material and texture in an option group, such as a single-select **Glow** group with **On** and **Off** options. Users get one download, with the glow as a checkbox.

Either way, a glow mod only covers the body mod and skin options its material came from. If you support both TBSE and Bibo, or several skin types, ship a material for each, for example as options in the glow mod.

**Put this in your mod description:**

- Requires the **Luminis** mod.
- Load order: body mod, then tattoo mod, then Luminis, then this glow mod (highest priority).
- Glows in darkness by default; fine-tune it in Penumbra's material editor under **Luminis Glow**.

## Eyes

Eyes have five **Glow area** choices:

| Glow area | What glows | Needs painting? |
| --- | --- | --- |
| **Natural iris** (default) | Just the iris, using the game's own iris shape | No |
| **Glow layer** | A PNG glow layer, like tattoos | Yes |
| **Painted eye mask** | The eye mask texture's alpha (advanced) | Yes |
| **Whole eye** | Iris, pupil and whites | No |
| **Emissive mask** | The glow area of a "glow editable" eye mod (the eye mask's red channel) | No |

**The natural glowing eye (no painting).** Give the eye material Luminis settings and turn up **Glow intensity**: by default it uses **Natural iris** and **Color source 1**, so the iris glows in the character's own eye color while the pupil and whites stay normal. For a different color, set **Color source** to 0 and pick a **Glow tint**. Heterochromia works automatically, since each eye uses its own color.

**Custom designs: an eye glow layer.** Paint a PNG over the eye texture's layout, with the glowing parts in any colors and everything else transparent, and run `make_glow_mod.py` with the eye material. It sets **Glow area: Glow layer** and **Color source: 2** for you.

1. In Penumbra's **Textures** tab, enter `chara/common/texture/eye/eye01_mask.tex` and **Export as PNG**. The blue circle in it marks the iris.
2. In Photoshop, scale it up to 512×512 (any square power of two works; larger gives crisper detail), add a new layer, and paint the glow over the iris. For a rainbow wheel, select the iris circle and use the Gradient tool in **Angle** mode with a spectrum preset. Delete a small circle in the middle to keep the pupil dark. Hide the reference layer and **Export as PNG**.
3. Make the glow mod with the eye material (export it from the On-Screen tab; for a Viera male with face 1 it's `mt_c1701f0001_iri_a.mtrl`):

```
python tools\make_glow_mod.py --name "My Eyes - Glow" --layer rainbow_eye.png --material mt_c1701f0001_iri_a.mtrl chara/human/c1701/obj/face/f0001/material/mt_c1701f0001_iri_a.mtrl
```

The painted design follows the iris, including as the pupil changes size. Each race and face has its own eye material, so ship one per face you support.

**Advanced: the painted eye mask and hue map.** For eye mods that already ship their own eye textures, the glow can also live in two spare channels: paint where it glows into the **alpha of the eye mask** (save as BC7, since vanilla BC1 masks only keep an on/off alpha) and set **Glow area: Painted eye mask**. With **Color source 2**, colors come from gray values painted into the alpha of the eye's color texture (`eye11_base.tex`): 0 red, 21 orange, 43 yellow, 85 green, 128 cyan, 170 blue, 191 purple, 213 magenta. Paint those alpha channels in Photoshop from a **TGA** export (not PNG, which discards colors under transparent pixels).

**"Glow editable" eye mods (Emissive mask).** Many eye mods ship their own glow, set with **g_EmissiveColor** and painted into the eye mask's red channel. Set **Glow area: Emissive mask** on the mod's eye material and **g_EmissiveColor** to black: Luminis then lights exactly that design, using the game's own brightness curve, with glow in darkness and animation on top.

## Hair

Hair needs no painting for the most common looks. The **Glow area** setting picks what glows:

| Glow area | What glows |
| --- | --- |
| Whole hair | Every strand |
| Highlights only | The highlight streaks (where the highlight color shows) |
| Main color only | Everything except the highlights |
| Luminis texture | A painted glow layer, like skin |

**Different colors for main hair and highlights:** turn on **Separate highlight color**, then set **Glow tint** for the main hair and **Highlight glow color** for the streaks. For pure colors (for example red hair with blue highlights), set **Color source** to 0. With 1, the tints multiply the character's actual hair and highlight colors, for subtler results.

**Rainbow:** **Color source** 3 runs a rainbow along the strands. **Rainbow length** sets how many times it repeats (negative values reverse it), and **Rainbow shift** moves the colors.

**Painted glow for custom hair:** a glow layer works exactly like skin. Paint a PNG over the hair's own texture layout (export its normal or mask texture from Penumbra as a reference) and use `make_glow_mod.py` with the hair material. It sets Glow area to **Luminis texture** automatically:

```
python tools\make_glow_mod.py --name "My Hair - Glow" --layer hair_glow.png --material mt_c1701h0004_hir_a.mtrl chara/human/c1701/obj/hair/h0004/material/v0001/mt_c1701h0004_hir_a.mtrl
```

The glow layer goes in the material's **Luminis glow layer** texture slot, the same slot eyes and skin use, so it works on every hairstyle.

## Gear, minions and mounts

Gear, minions, mounts and weapons use `characterlegacy.shpk` (most items) or `character.shpk` (newer ones), the **Gear** and **Gear (newer)** parts of Luminis. Their **Glow area** has three choices:

| Glow area | What glows |
| --- | --- |
| **Glow layer** | A painted glow layer (g_SamplerLuminis), drawn over the item's own UV layout |
| **Whole item** | Everything using the material |
| **Color table emissive** | Each color table row, in its own **Emissive Color** (rows left black don't glow) |

**Color table emissive** needs no painting: set an Emissive Color on each row that should glow, then use **Color source 2** for the rows' own colors. The game's own always-on row glow switches off automatically in this mode. Hovering a row's crosshair button in the Color Table highlights its part on the character. Soft emissive colors need a higher **Glow intensity** (up to about 6).

**Per-row control (Luminis Rows):** each of **Row 01** to **Row 16** can be **Animated** (follows the Animation, the default), **Static** (glows steadily) or **Off**. For example, a hoodie's fabric row on Static stays one color while its logo row on Animated cycles through chroma. Rows apply in every gear glow area, and control layer 1.

A glow on a minion or mount uses its owner's collection.

## Animation

Every glow (eyes, hair and skin, layer 1 and layer 2) can change over time. The settings are in the **Luminis Animation** section (and **Luminis Layer 2** for the second layer).

| Animation | What it does | Colors used |
| --- | --- | --- |
| **Off** | A steady glow (default) | |
| **Blink** | Switches between the glow and nothing: a hard flash or a smooth pulse | The glow's own colors |
| **Pulse** | Like Blink, but breathes between **Pulse minimum** and **Pulse maximum** (fractions of the intensity, 0.15 = 15%) instead of going dark | The glow's own colors |
| **Two-color** | Alternates between two colors | Glow tint and Color 2 |
| **Color steps** | Steps through 2 to 12 evenly spaced rainbow colors (Steps); Rainbow shift picks the starting color | Rainbow |
| **Chroma** | Spins smoothly through the whole rainbow; on hair and skin, Rainbow length above 0 adds moving color bands | Rainbow |
| **Custom colors** | Cycles through 2 to 4 colors you pick (Steps sets how many) | Glow tint, Color 2, Color 3, Color 4 |
| **Hue cycle** | Rotates every color around the color wheel at once, so a painted rainbow gradient flows through the design | The color source's own colors (use Color source 2) |

- **Speed** sets how fast it cycles. Small values are slow (0.005 is barely noticeable, 0.2 is a gentle cycle), larger values strobe; negative values run backwards. **Debug view: Clock** shows the game clock that drives it.
- **Softness** blends between a hard switch (0) and a smooth fade (1).
- Animated colors follow the **brightness** of the color source, not its hue: dark parts (an eye's pupil, dark painted lines) stay dark, while brightly painted parts of any color take the animation colors at full strength. To keep a painted gradient's own colors and make them flow, use **Hue cycle**; Chroma turns the whole glow one color at a time.

## Glow layer 2

Skin, hair and eye materials can have a **second glow layer**, with its own painting, intensity, tint, color source, **light behavior** and **animation**. For example, one design always on in its painted colors and a second one that only glows in darkness, cycling through chroma.

- **The texture** goes in the material's **g_SamplerLuminis2** slot (layer 1 uses **g_SamplerLuminis**). With `make_glow_mod.py`, use `--layer2` and its options; by hand, fill the second `dummy.tex` row in the material editor.
- **Its settings** are in the **Luminis Layer 2** section: Layer 2 intensity (0 = off), tint, color source, glow mode, dark start and end, light sensitivity, animation, speed, steps, softness, and its own colors 2 to 4. **Layer 2 color source 0** makes its animation colors pure, using the painting only to decide where it glows.
- **Shared with layer 1:** area mix, detail, and rainbow length and shift.
- **Where both layers overlap, their glow adds up**, so colors mix and brighten. Paint them side by side for separate effects.
- **Debug views** Layer 2 mask and Layer 2 light gate show what layer 2 sees.

## Settings reference

All settings appear in Penumbra's material editor (**Advanced Editing > Materials**) under **Luminis Glow**, with a hover description on each. Changes apply live; click **Save to File** to keep them.

| Setting | What it does | Typical values |
| --- | --- | --- |
| Glow intensity | Brightness. 0 turns Luminis off for the material | 0.8 to 2; higher blooms more |
| Glow tint | Multiplies the glow color; white keeps the source colors. Color 1 for Two-color and Custom colors | White |
| Glow mode | Always on, Glow in darkness, or Glow in light | Glow in darkness |
| Dark start / Dark end | Light levels where the glow is fully on / fully off. The gap sets how gradually it fades | 0.02 / 0.15 |
| Light sensitivity | How strongly the mode applies; 0 ignores lighting | 1 |
| Area mix | 0 reacts to light hitting the surface (shadows, facing a lamp); 1 to the area's overall brightness (steady while turning) | 0.5 |
| Color source | 0 tint only, 1 the surface's own color, 2 glow layer (or hue map), 3 rainbow (hair and skin); values in between blend | Glow layer: 2; natural eye: 1 |
| Glow area | Where it glows (options differ for eyes, hair and skin) | Eyes: Natural iris; skin: Glow layer |
| Detail / Detail gain | Lets the surface's own light and dark pattern show through the glow, so it reads as translucent | 0, or 0.7 to 1 with gain 2 to 4 |
| Rainbow length / shift | Rainbow repeats and offset (color source 3, chroma, color steps) | 1 / 0 |
| Separate highlight color | Hair only: highlights use Highlight glow color | Off |
| Animation, Speed, Steps, Softness | Animation (see Animation) | Off; speed 0.2; softness 1 |
| Pulse minimum / maximum | Pulse's lowest and highest brightness, as fractions of the intensity | 0.15 / 1 |
| Luminis Rows (gear) | Row 01 to Row 16: Animated, Static or Off (see Gear) | Animated |
| Color 2, Color 3, Color 4 | Extra colors for Two-color and Custom colors | |
| Luminis Layer 2 settings | Glow layer 2's own intensity, tint, color source, light behavior, animation and colors (see Glow layer 2) | Intensity 0 = off |
| Debug view | Glow mask, Light level, Light gate, Glow only, Clock, Layer 2 mask, Layer 2 light gate, for diagnosing; set back to Off | Off |

**Tuning tips:**

- To set the light thresholds, use **Debug view: Light gate** and walk between light and dark places, or step a housing interior's brightness slider. White means glowing, black means off.
- If a design blurs into a blob, lower the intensity: strong glow blooms beyond its edges.
- Settings are per material, so a tattoo and the eyes on the same character can glow differently.

## Converting existing mods

`luminis_convert_mod.py` makes a Luminis copy of any Penumbra mod, a folder or a `.pmp`. Every eye, hair and skin material in it gets the Luminis settings; everything else is copied unchanged, and the original is never touched.

```
python tools\luminis_convert_mod.py "D:\SquareEnix\Some Eye Mod"
```

It creates "Some Eye Mod (Luminis)" next to your other mods. In Penumbra, use **Settings > Rediscover Mods**, disable the original, and enable the copy. It accepts the same settings options as `mtrl_luminis.py` (`--color`, `--light`, `--misc`, `--detail`, `--highlight`) to set starting values.

Good uses:

- **Eye mods:** converted eyes glow right away as a **natural iris** in their own colors (eyes start at intensity 1.5). For custom designs, add a glow layer as described under Eyes.
- **Hair mods:** converted hair can glow as a whole, by highlights or by main color, with no painting.
- **Body and tattoo mods:** skin materials start at intensity **0**, because many body mods' textures would otherwise make the whole body glow. Turn intensity up and attach a glow layer with `make_glow_mod.py`, or with `mtrl_luminis.py --glow-texture`.

An eye or hair glow mod is simply a converted (or hand-edited) material plus any textures you changed, so the sharing advice above applies to those too.

## Moving settings between materials

`luminis_settings.py` exports a material's Luminis settings (and its glow layer paths) to a small JSON file, and imports them into other materials. That's handy when a tattoo gets a new version, or to share a look. Double-click **Luminis Settings.bat** for a window with **Export**, **Import** and **Copy material to material** buttons, and checkboxes for which parts to import (Glow, Animation, Layer 2, Color table rows, glow layer paths). Or from the command line:

```
python tools\luminis_settings.py export old_tattoo.mtrl tattoo.luminis.json
python tools\luminis_settings.py import tattoo.luminis.json new_tattoo.mtrl [--no-textures] [--only glow,animation]
python tools\luminis_settings.py copy old_tattoo.mtrl new_tattoo.mtrl
```

Every changed material is backed up as `NAME.mtrl.bak` first. Afterwards, click **Reload Mod** in Penumbra and redraw.

## Two models on one item

Two accessory mods that replace the same slot can't both show, since one item shows one model. `mdl_merge.py` merges two simple models (single detail level, no shape keys, which covers most accessories, ears and horns) into one, checks the result, and lists the materials to carry over:

```
python tools\mdl_merge.py keep.mdl add.mdl out\keep.mdl
```

Put the merged model on the kept item, and redirect the added model's materials under the kept item's folder (`chara/accessory/a<item>/material/v0001/...`). When the tool stops, merge in Blender through Penumbra's glTF export and import instead.

## Troubleshooting

Penumbra's **On-Screen** tab answers most questions: expand the material and check which mod provides each file in the right-hand column.

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Nothing glows | Intensity 0, glow mode Glow in darkness in a bright place, or Luminis not enabled | Set Glow mode to Always on to test; check Luminis is enabled and the material shows the Luminis Glow section |
| No Luminis Glow section in the material editor | Luminis disabled, or another mod's shader package wins | Enable Luminis and raise its priority above other mods replacing the same shader |
| No g_SamplerLuminis row, or no Glow area, Animation or Layer 2 settings | An older Luminis version | Install the latest Luminis release and restart the game |
| The whole eye glows, pupil and whites included | Glow area set to Whole eye, or Painted eye mask with an unpainted mask | Set Glow area to Natural iris (or Glow layer with a painted layer) |
| Only part of the body glows | The glow is on a material that only covers part of the mesh | Find the material that covers the tattoo area in the On-Screen tab (for TBSE, `_b`) |
| The whole body glows | Glow area set to Whole skin, or a glow layer without transparency | Set Glow area to Glow layer; check the mask with Debug view: Glow mask |
| Skin looks lighter or tinted, even with intensity 0 | A texture override is replacing the skin's color texture | Check the material's g_SamplerDiffuse row in the On-Screen tab; it should come from the body mod |
| Animated colors are dark in places | Animation follows the painting's brightness, so dark painted areas stay dark | Paint the glowing parts brighter, or set the color source to 0 (tint only) |
| Settings show in Penumbra but change nothing | The game still runs the Luminis it loaded at startup | Fully restart the game after installing or updating Luminis |
| "The current material has not been found on your character" | Another mod replaces this material with a higher priority | Check the On-Screen tab for which mod wins; raise your glow mod's priority |
| A gear row ignores its Luminis Rows setting | Shaders older than 2.0, or the setting is on a different row | Restart after updating; use the row's crosshair button to find the right row |
| Layer 2 doesn't show | Layer 2 intensity 0, the texture in the wrong slot, or its glow mode in bright light | Raise Layer 2 intensity; check the texture is in g_SamplerLuminis2; try Layer 2 glow mode Always on |
| A new texture doesn't show up | The game keeps the old copy cached | Save new versions under a new file name, or restart the game |
| The design looks like a blurry blob | Viewing distance and bloom | Use bolder shapes, lower the intensity, check up close |
| Glow flickers while turning | Narrow light thresholds, or Area mix at 0 | Widen Dark start/end, raise Area mix to 0.5 or more |
| Everything stopped after a game patch | The shaders need updating for the new game version | Disable Luminis until an updated release is out |

Leftover **Debug view** settings are a common surprise: a debug view replaces the surface with diagnostic colors, so check it's set to **Off** when things look strange.
