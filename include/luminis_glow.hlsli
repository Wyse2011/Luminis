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
};

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
    float3 baseColor = source * tint * lerp(1.0, detailLum, detail);
    float  mask      = saturate(i.glowMask);

    LuminisOutput o;
    o.emissive    = baseColor * mask * intensity * gate;
    o.debugActive = (debugView != 0);
    o.debugColor  = float3(0.0, 0.0, 0.0);

    if (debugView == 1)      o.debugColor = mask.xxx;
    else if (debugView == 2) o.debugColor = lightLum.xxx;
    else if (debugView == 3) o.debugColor = gate.xxx;
    else if (debugView == 4) o.debugColor = o.emissive;

    return o;
}

#endif // LUMINIS_GLOW_HLSLI
