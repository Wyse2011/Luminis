// ============================================================================
// Luminis Glow - emissive + light-sensitivity block for patched FFXIV shaders
// Target: Shader Model 5 (fxc /T ps_5_0), Dawntrail-era skin/hair/iris .shpk
// ============================================================================
//
// MATERIAL CONSTANT LAYOUT
// 3 x float4 = 48 bytes. Append to the material cbuffer at a 16-byte aligned
// offset after the vanilla parameters, and declare them in the .shpk's
// material parameter list so Penumbra's material editor can expose them.
//
//  Slot  Name             .x            .y              .z               .w
//  +0    g_LuminisColor   tint R        tint G          tint B           intensity
//  +1    g_LuminisLight   dark start    dark end        mode             sensitivity
//  +2    g_LuminisMisc    color source  area mix        per-pixel sens.  debug view
//  +3    g_LuminisDetail  detail        detail gain     (reserved)       (reserved)
//
//  Color src:  0 = tint only, 1 = the surface's own color, 2 = glow map (eyes: hue painted in a
//              texture channel; hair: the Luminis texture's RGB), 3 = rainbow (hair: along the
//              strands); values in between blend, e.g. 1.5 = half surface color, half glow map
//  Detail:     0 = flat glow, 1 = glow carries the surface's own light/dark detail (pupil,
//              fibers, painted shading); gain brightens that detail (default 2)
//  Modes:      0 = always on, 1 = glow in darkness, 2 = glow in light
//  Area mix:   0 = react to light hitting each pixel (facing, shadows), 1 = react to
//              overall area brightness only, values between blend the two
//  Debug view: 0 = off, 1 = mask, 2 = light brightness, 3 = light gate,
//              4 = final emissive only
//
// SHPK DEFAULTS (what unmodified materials get)
//  g_LuminisColor = (1, 1, 1, 0)       <- intensity 0: never glows by accident
//  g_LuminisLight = (0.05, 0.35, 1, 1)
//  g_LuminisMisc  = (1, 0.5, 0, 0)
//
// Suggested authoring starting point: intensity 1-4, then tune dark start/end
// per zone. Values above 1 may trigger bloom depending on post-processing.
// ============================================================================

#ifndef LUMINIS_GLOW_HLSLI
#define LUMINIS_GLOW_HLSLI

// The patched shader must map these to its material cbuffer before including,
// e.g.  #define LUMINIS_P0 g_MaterialParameter[LUMINIS_BASE + 0]
#if !defined(LUMINIS_P0) || !defined(LUMINIS_P1) || !defined(LUMINIS_P2)
  #error "Define LUMINIS_P0, LUMINIS_P1 and LUMINIS_P2 before including luminis_glow.hlsli"
#endif
#ifndef LUMINIS_P3
  #define LUMINIS_P3 float4(0.0, 2.0, 0.0, 0.0)   // detail off
#endif

#define LUMINIS_MODE_ALWAYS 0
#define LUMINIS_MODE_DARK   1
#define LUMINIS_MODE_LIGHT  2

struct LuminisInput
{
    float3 albedo;            // linear diffuse color for this pixel (after tattoo/skin blending)
    float3 tint;              // glow tint (usually g_LuminisColor.rgb; hair can vary it per area)
    float  glowMask;          // 0..1 from the repurposed texture channel
    float3 glowColor;         // glow map color, linear (eyes: from the hue map; hair: Luminis texture RGB)
    float  rainbowHue;        // hue for the rainbow color source (eyes: the hue map; hair: along the strands)
    float  pixelSensitivity;  // 0..1 from a second free channel, or 1.0 if none
    float3 lightDiffuse;      // diffuse light read from the lighting buffer
    float3 ambient;           // overall area brightness (direction-independent), used by area mix
    float  time;              // game clock (g_PbrParameterCommon m_LoopTime), drives animation
    float4 layer2;            // glow layer 2 texture sample (RGB = colors, alpha = where it glows)
    float  animate;           // 1 = layer 1 follows its animation here, 0 = steady (gear: per color table row)
};

// Animation settings (g_LuminisAnim, g_LuminisAnimColor). Shaders built before animation existed
// don't define them; these defaults mean "no animation".
#ifndef LUMINIS_P5
#define LUMINIS_P5 float4(0.0, 1.0, 4.0, 1.0)
#endif
#ifndef LUMINIS_P6
#define LUMINIS_P6 float4(0.0, 0.0, 1.0, 0.0)
#endif
// P7.w / P8.w: Pulse minimum / maximum, as fractions of the intensity (a maximum of 0 means 1).
#ifndef LUMINIS_P7
#define LUMINIS_P7 float4(0.0, 1.0, 0.0, 0.15)
#endif
#ifndef LUMINIS_P8
#define LUMINIS_P8 float4(1.0, 1.0, 0.0, 1.0)
#endif
// Glow layer 2: its own tint and intensity (P9), light behavior (P10: dark start, dark end, mode,
// sensitivity) and animation (P11: mode, speed, steps, softness). Intensity 0 = off.
#ifndef LUMINIS_P9
#define LUMINIS_P9 float4(1.0, 1.0, 1.0, 0.0)
#endif
#ifndef LUMINIS_P10
#define LUMINIS_P10 float4(0.02, 0.15, 0.0, 1.0)
#endif
#ifndef LUMINIS_P11
#define LUMINIS_P11 float4(0.0, 1.0, 4.0, 1.0)
#endif
// Glow layer 2's own animation colors 2, 3 and 4 (its Layer 2 tint is color 1).
// P12.w is layer 2's color source: 0 tint only, 1 surface color, 2 its painted colors, 3 rainbow.
#ifndef LUMINIS_P12
#define LUMINIS_P12 float4(0.0, 0.0, 1.0, 2.0)
#endif
// P13.w / P14.w: layer 2's Pulse minimum / maximum.
#ifndef LUMINIS_P13
#define LUMINIS_P13 float4(0.0, 1.0, 0.0, 0.15)
#endif
#ifndef LUMINIS_P14
#define LUMINIS_P14 float4(1.0, 1.0, 0.0, 1.0)
#endif

struct LuminisOutput
{
    float3 emissive;          // add to the final color
    bool   debugActive;       // true when a debug view is selected
    float3 debugColor;        // replaces the final color when debugActive
};

// Fully saturated color for a hue in 0..1 (0 = red, 1/6 = yellow, 1/3 = green, 1/2 = cyan,
// 2/3 = blue, 5/6 = magenta, 1 = red). Returned in linear space.
float3 Luminis_HueToRGB(float h)
{
    h = frac(h);
    float3 c = saturate(float3(abs(h * 6.0 - 3.0) - 1.0, 2.0 - abs(h * 6.0 - 2.0), 2.0 - abs(h * 6.0 - 4.0)));
    return c * c;   // approximate sRGB -> linear so mid hues aren't washed out
}

float Luminis_Luminance(float3 c)
{
    return dot(c, float3(0.2126, 0.7152, 0.0722));
}

// Returns 0..1: how much the glow is allowed through at this light level.
float Luminis_LightGate(float lightLum, float mode, float darkStart, float darkEnd, float sensitivity)
{
    // Guard against bad material values (start >= end would break smoothstep)
    float hi = max(darkEnd, darkStart + 1e-4);
    float brightness = smoothstep(darkStart, hi, lightLum); // 0 = dark, 1 = bright

    int m = (int)round(mode);
    float gate = 1.0;
    if (m == LUMINIS_MODE_DARK)       gate = 1.0 - brightness;
    else if (m == LUMINIS_MODE_LIGHT) gate = brightness;

    // sensitivity 0 = ignore lighting entirely, 1 = full effect of the mode
    return lerp(1.0, gate, saturate(sensitivity));
}

// Animation shared by glow layer 1 and layer 2. Returns the animated glow color; gain is the
// blink factor (1 when not blinking). Animated colors are scaled by the color source's brightness,
// so dark parts of the surface (an eye's pupil, dark lines) stay dark.
//   an: mode (0 off, 1 blink, 2 two-color, 3 color steps, 4 chroma, 5 custom colors, 6 pulse,
//       7 hue cycle: every color rotates around the color wheel, so painted gradients flow),
//       speed, steps, softness
//   pulse: minimum and maximum brightness for Pulse, as fractions of the intensity (max 0 = 1)
// Rotates a color's hue by 'shift' turns of the color wheel, keeping its saturation and brightness.
float3 Luminis_HueRotate(float3 c, float shift)
{
    float4 K = float4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    float4 p = lerp(float4(c.bg, K.wz), float4(c.gb, K.xy), step(c.b, c.g));
    float4 q = lerp(float4(p.xyw, c.r), float4(c.r, p.yzx), step(p.x, c.r));
    float  d = q.x - min(q.w, q.y);
    float3 hsv = float3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
    hsv.x = frac(hsv.x + shift);
    float3 rgb = saturate(abs(frac(hsv.xxx + float3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0);
    return hsv.z * lerp(float3(1.0, 1.0, 1.0), rgb, hsv.y);
}

float3 Luminis_Animate(float3 source, float3 tint, float3 c2, float3 c3, float3 c4, float detailF,
                       float4 an, float2 pulse, float time, float rainbowHue, float shift, out float gain)
{
    float  animMode = round(an.x);
    float  phase    = frac(time * an.y);
    float  soft     = saturate(an.w);
    float  wave     = lerp(phase < 0.5 ? 1.0 : 0.0, 0.5 + 0.5 * cos(6.2831853 * phase), soft);
    float3 color    = source * tint * detailF;
    // Animated colors use the source's brightness (its strongest channel), not its color: dark parts
    // (a pupil, dark lines) stay dark, while brightly colored paint of any hue takes the animation
    // color at full strength instead of cancelling out (green paint x red = black).
    float  bright   = max(max(source.r, source.g), source.b);
    gain = 1.0;
    if (animMode > 0.5 && animMode < 1.5) {
        gain = wave;
    } else if (animMode > 6.5) {
        color = Luminis_HueRotate(source, phase) * tint * detailF;
    } else if (animMode > 5.5) {
        float pmax = pulse.y > 0.0 ? pulse.y : 1.0;
        gain = lerp(max(pulse.x, 0.0), pmax, wave);
    } else if (animMode > 1.5 && animMode < 2.5) {
        color = bright * lerp(c2, tint, wave) * detailF;
    } else if (animMode > 2.5 && animMode < 4.5) {
        float hue;
        if (animMode < 3.5) {
            float steps = clamp(round(an.z), 2.0, 12.0);
            float t     = phase * steps;
            float idx   = floor(t);
            float f     = soft > 0.001 ? saturate((t - idx - (1.0 - soft)) / soft) : 0.0;
            hue = (idx + f * f * (3.0 - 2.0 * f)) / steps + shift;
        } else {
            hue = phase + rainbowHue;
        }
        color = bright * Luminis_HueToRGB(frac(hue)) * detailF;
    } else if (animMode > 4.5 && animMode < 5.5) {
        float  count = clamp(round(an.z), 2.0, 4.0);
        float  t     = phase * count;
        float  idx   = floor(t);
        float  f     = soft > 0.001 ? saturate((t - idx - (1.0 - soft)) / soft) : 0.0;
        f = f * f * (3.0 - 2.0 * f);
        float  nxt   = idx + 1.0 >= count ? 0.0 : idx + 1.0;
        float3 a     = idx < 0.5 ? tint : (idx < 1.5 ? c2 : (idx < 2.5 ? c3 : c4));
        float3 b     = nxt < 0.5 ? tint : (nxt < 1.5 ? c2 : (nxt < 2.5 ? c3 : c4));
        color = bright * lerp(a, b, f) * detailF;
    }
    return color;
}

LuminisOutput Luminis_Evaluate(LuminisInput i)
{
    float4 p0 = LUMINIS_P0;
    float4 p1 = LUMINIS_P1;
    float4 p2 = LUMINIS_P2;
    float4 p3 = LUMINIS_P3;

    float3 tint       = i.tint;
    float  intensity  = max(p0.w, 0.0);
    float  darkStart  = p1.x;
    float  darkEnd    = p1.y;
    float  mode       = p1.z;
    float  matSens    = p1.w;
    float  colorSrc   = clamp(p2.x, 0.0, 3.0);  // 0 tint, 1 surface color, 2 glow map, 3 rainbow
    float  ambientW   = saturate(p2.y);   // area mix (see below)
    float  usePixSens = saturate(p2.z);   // 1 = read per-pixel sensitivity channel
    int    debugView  = (int)round(p2.w);

    // Area mix: 0 = light hitting this pixel (reacts to facing and shadows),
    //           1 = overall area brightness (stable as the character turns).
    float lightLum = Luminis_Luminance(lerp(i.lightDiffuse, i.ambient, ambientW));

    float sens = matSens * lerp(1.0, saturate(i.pixelSensitivity), usePixSens);
    float gate = Luminis_LightGate(lightLum, mode, darkStart, darkEnd, sens);

    float3 rainbow   = Luminis_HueToRGB(i.rainbowHue);
    float3 source    = colorSrc <= 1.0 ? lerp(float3(1.0, 1.0, 1.0), i.albedo, colorSrc)
                     : colorSrc <= 2.0 ? lerp(i.albedo, i.glowColor, colorSrc - 1.0)
                                       : lerp(i.glowColor, rainbow, colorSrc - 2.0);
    // Detail: let the surface's own light/dark pattern show through the glow, so dark parts
    // (pupil, fibers, painted lines) glow less and the glow reads as translucent.
    float  detail    = saturate(p3.x);
    float  detailLum = saturate(Luminis_Luminance(i.albedo) * max(p3.y, 0.0));
    float  detailF   = lerp(1.0, detailLum, detail);
    float3 baseColor = source * tint * detailF;
    float  mask      = saturate(i.glowMask);

    float  animGain;
    float4 anim1 = LUMINIS_P5;
    anim1.x *= step(0.5, i.animate);
    baseColor = Luminis_Animate(source, tint, LUMINIS_P6.rgb, LUMINIS_P7.rgb, LUMINIS_P8.rgb, detailF,
                                anim1, float2(LUMINIS_P7.w, LUMINIS_P8.w), i.time, i.rainbowHue, p3.w, animGain);

    // ---- Glow layer 2: own colors (its texture), tint, intensity, light behavior and animation ----
    float4 l2c      = LUMINIS_P9;
    float4 l2l      = LUMINIS_P10;
    float  l2mask   = saturate(i.layer2.w);
    float  l2gate   = Luminis_LightGate(lightLum, l2l.z, l2l.x, l2l.y, l2l.w);
    float  l2gain;
    float  l2cs     = clamp(LUMINIS_P12.w, 0.0, 3.0);
    float3 l2paint  = i.layer2.rgb * i.layer2.rgb;
    float3 l2src    = l2cs <= 1.0 ? lerp(float3(1.0, 1.0, 1.0), i.albedo, l2cs)
                    : l2cs <= 2.0 ? lerp(i.albedo, l2paint, l2cs - 1.0)
                                  : lerp(l2paint, rainbow, l2cs - 2.0);
    float3 l2color  = Luminis_Animate(l2src, l2c.rgb, LUMINIS_P12.rgb, LUMINIS_P13.rgb,
                                      LUMINIS_P14.rgb, detailF, LUMINIS_P11, float2(LUMINIS_P13.w, LUMINIS_P14.w),
                                      i.time, i.rainbowHue, p3.w, l2gain);
    float3 l2emit   = l2color * l2mask * max(l2c.w, 0.0) * l2gate * l2gain;

    LuminisOutput o;
    o.emissive    = baseColor * mask * intensity * gate * animGain + l2emit;
    o.debugActive = (debugView != 0);
    o.debugColor  = float3(0.0, 0.0, 0.0);

    if (debugView == 1)      o.debugColor = mask.xxx;
    else if (debugView == 2) o.debugColor = lightLum.xxx;
    else if (debugView == 3) o.debugColor = gate.xxx;
    else if (debugView == 4) o.debugColor = o.emissive;
    else if (debugView == 5) o.debugColor = frac(i.time).xxx;    // clock: one black-to-white sweep per clock unit
    else if (debugView == 6) o.debugColor = l2mask.xxx;          // glow layer 2 mask
    else if (debugView == 7) o.debugColor = l2gate.xxx;          // glow layer 2 light gate

    return o;
}

#endif // LUMINIS_GLOW_HLSLI
