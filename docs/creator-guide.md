# Luminis Creator Guide

## What Luminis is

Luminis adds light-sensitive, multi-color glow to eyes, hair and skin in Dawntrail. It's the spiritual successor to Atramentum Luminis, rebuilt from scratch for the 7.x shaders.

It works in three layers, each a separate Penumbra mod:

| Layer | What it contains | Who makes it |
| --- | --- | --- |
| **Luminis** (the framework) | Replacement eye, hair and skin shaders, plus the dev-kit files that add the Luminis Glow controls to Penumbra | Installed once by every user |
| **Tattoo or body mod** | The normal look: TBSE or Bibo, tattoos painted into the color texture | Body and tattoo artists, as today |
| **Glow mod** | A Luminis copy of the material plus a glow layer texture that says what glows, and in which colors | You, with `make_glow_mod.py` |

On its own, the framework changes nothing you can see. A material glows only when it has Luminis settings with an intensity above 0, and that's exactly what glow mods provide. Because the glow lives in its own mod, users can switch it on and off without touching the tattoo.

**Load order (Penumbra priority, highest last):**

1. Body mod (TBSE, Bibo, ...)
2. Tattoo mod
3. Luminis
4. Glow mods

Glow mods must sit above the body mod, because they replace its material. Luminis must sit above anything else that replaces `iris.shpk`, `hair.shpk` or `skin.shpk`.

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
| `--material FILE GAME_PATH` | A material to make glow, with its game path. Repeat it for several materials that share the layer | (required) |
| `--intensity` | Glow brightness | 1.5 |
| `--mode` | `dark` (glow in darkness), `always`, or `light` (glow in light) | dark |
| `--tint R,G,B` | Multiplies the layer's colors; `1,1,1` keeps them as painted | 1,1,1 |
| `--area-mix` | 0 = react to light hitting the skin, 1 = to the area's overall brightness | 0.5 |
| `--layer-path` | Where the glow texture goes in-game | Next to the material's textures |
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

Eyes use two channels of the textures the eye material already has, so an eye glow mod ships modified copies of those textures plus a material with Luminis settings.

**Where it glows: the eye mask's alpha.** The eye mask texture (for example `chara/common/texture/eye/eye01_mask.tex`) uses red, green and blue for the eye's normal look, but the game never reads its alpha. Paint the glow there: white glows, black doesn't, gray glows partly. Vanilla masks are BC1, which only keeps an on/off alpha, so save glow masks as **BC7**.

**What color it glows** depends on **Color source**:

- **1, eye color:** the glow uses the eye's own colors, including the player's chosen eye color (heterochromia gives each eye its own glow).
- **2, hue map:** colors painted as gray values into the alpha of the eye's color texture (for example `eye11_base.tex`). The eye looks normal until it glows. Each gray value is one color:

| Color | Gray value (0 to 255) |
| --- | --- |
| Red | 0 |
| Orange | 21 |
| Yellow | 43 |
| Green | 85 |
| Cyan | 128 |
| Blue | 170 |
| Purple | 191 |
| Magenta | 213 |

A black-to-white **angle gradient** around the pupil gives a full rainbow. Flat regions of two gray values give two colors, for example 0 and 85 for red and green.

**Painting eye textures in Photoshop:** export from Penumbra as **TGA**, not PNG, because Photoshop discards the colors under transparent pixels in PNGs, which would damage the eye's normal look. Paint in the **Alpha 1** channel (in the Channels panel), using the Classic gradient mode for gradients, and save as TGA. Then, in Penumbra, load the TGA, set the output to BC7, and **Save as TEX**.

**Size:** the iris is only about 50 pixels across in a 128×128 eye mask, so bold shapes read best. Detail is visible close up.

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

A few hairstyles use the game's decal texture on their hair; on those, **Luminis texture** mode reads the decal instead, so use the other glow areas there.

## Settings reference

All settings appear in Penumbra's material editor (**Advanced Editing > Materials**) under **Luminis Glow**, with a hover description on each. Changes apply live; click **Save to File** to keep them.

| Setting | What it does | Typical values |
| --- | --- | --- |
| Glow intensity | Brightness. 0 turns Luminis off for the material | 0.8 to 2; higher blooms more |
| Glow tint | Multiplies the glow color; white keeps the source colors | White |
| Glow mode | Always on, Glow in darkness, or Glow in light | Glow in darkness |
| Dark start / Dark end | Light levels where the glow is fully on / fully off. The gap sets how gradually it fades | 0.02 / 0.15 |
| Light sensitivity | How strongly the mode applies; 0 ignores lighting | 1 |
| Area mix | 0 reacts to light hitting the surface (shadows, facing a lamp); 1 to the area's overall brightness (steady while turning) | 0.5 |
| Color source | 0 tint only, 1 the surface's own color, 2 glow map or glow layer, 3 rainbow; values in between blend | Skin and hair layers: 2 |
| Glow area | Where it glows (options differ for eyes, hair and skin) | Glow layer / Luminis texture |
| Detail / Detail gain | Lets the surface's own light and dark pattern show through the glow, so it reads as translucent | 0, or 0.7 to 1 with gain 2 to 4 |
| Rainbow length / shift | Rainbow repeats and offset (color source 3) | 1 / 0 |
| Separate highlight color | Hair only: highlights use Highlight glow color | Off |
| Debug view | Glow mask, Light level, Light gate or Glow only, for diagnosing; set back to Off | Off |

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

- **Eye mods:** converted eyes glow with their own colors right away (eyes start at intensity 1.5). For painted designs, add a glow mask to the eye mask's alpha as described under Eyes.
- **Hair mods:** converted hair can glow as a whole, by highlights or by main color, with no painting.
- **Body and tattoo mods:** skin materials start at intensity **0**, because many body mods' textures would otherwise make the whole body glow. Turn intensity up and attach a glow layer with `make_glow_mod.py`, or with `mtrl_luminis.py --glow-texture`.

An eye or hair glow mod is simply a converted (or hand-edited) material plus any textures you changed, so the sharing advice above applies to those too.

## Troubleshooting

Penumbra's **On-Screen** tab answers most questions: expand the material and check which mod provides each file in the right-hand column.

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Nothing glows | Intensity 0, glow mode Glow in darkness in a bright place, or Luminis not enabled | Set Glow mode to Always on to test; check Luminis is enabled and the material shows the Luminis Glow section |
| No Luminis Glow section in the material editor | Luminis disabled, or another mod's shader package wins | Enable Luminis and raise its priority above other mods replacing the same shader |
| Only part of the body glows | The glow is on a material that only covers part of the mesh | Find the material that covers the tattoo area in the On-Screen tab (for TBSE, `_b`) |
| The whole body glows | Glow area set to Whole skin, or a glow layer without transparency | Set Glow area to Glow layer; check the mask with Debug view: Glow mask |
| Skin looks lighter or tinted, even with intensity 0 | A texture override is replacing the skin's color texture | Check the material's g_SamplerDiffuse row in the On-Screen tab; it should come from the body mod |
| A new texture doesn't show up | The game keeps the old copy cached | Save new versions under a new file name, or restart the game |
| The design looks like a blurry blob | Viewing distance and bloom | Use bolder shapes, lower the intensity, check up close |
| Glow flickers while turning | Narrow light thresholds, or Area mix at 0 | Widen Dark start/end, raise Area mix to 0.5 or more |
| Everything stopped after a game patch | The shaders need updating for the new game version | Disable Luminis until an updated release is out |

Leftover **Debug view** settings are a common surprise: a debug view replaces the surface with diagnostic colors, so check it's set to **Off** when things look strange.
