# luminis_asm.py - build Luminis versions of composite pixel shaders by patching their assembly.
#
# Usage (from D:\luminis):
#   python tools\luminis_asm.py PROFILE OUT_DIR INDEX [INDEX ...]
#
#   PROFILE  iris, hair, skin, characterlegacy or character
#
# For each pixel shader index it disassembles blobs\<profile>\all\ps_<N>.dxbc, compiles a small
# HLSL "epilogue" (include\luminis_glow.hlsli plus profile-specific setup) with fxc for this
# shader's registers, splices it in just before the final color is written, and reassembles
# with the original signatures. Shaders that don't fit are reported and skipped.
# Writes OUT_DIR\ps_<N>.dxbc and OUT_DIR\bindings.json (the extra texture binding each needs).
import json, pathlib, re, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DECOMPILER = ROOT / "tools" / "3dmigoto" / "cmd_Decompiler.exe"
INCLUDE = ROOT / "include"
MATERIAL_REGS = 45  # g_MaterialParameter size including the Luminis slots 26..44

COMMON_HEADER = r"""
cbuffer cbMat     : register(b0)     {{ float4 g_MaterialParameter[{regs}]; }}
cbuffer cbAmbient : register(b{amb}) {{ float4 g_AmbientParam[10]; }}
#define LUMINIS_P0 g_MaterialParameter[26]
#define LUMINIS_P1 g_MaterialParameter[27]
#define LUMINIS_P2 g_MaterialParameter[28]
#define LUMINIS_P3 g_MaterialParameter[29]
#define LUMINIS_P4 g_MaterialParameter[30]
#define LUMINIS_P5 g_MaterialParameter[31]
#define LUMINIS_P6 g_MaterialParameter[32]
#define LUMINIS_P7 g_MaterialParameter[33]
#define LUMINIS_P8 g_MaterialParameter[34]
#define LUMINIS_P9 g_MaterialParameter[35]
#define LUMINIS_P10 g_MaterialParameter[36]
#define LUMINIS_P11 g_MaterialParameter[37]
#define LUMINIS_ROWS_BASE 41
#define LUMINIS_P12 g_MaterialParameter[38]
#define LUMINIS_P13 g_MaterialParameter[39]
#define LUMINIS_P14 g_MaterialParameter[40]
#include "luminis_glow.hlsli"

float3 Luminis_Area() {{
    return g_AmbientParam[3].w * saturate(float3(g_AmbientParam[0].w, g_AmbientParam[1].w, g_AmbientParam[2].w));
}}
float Luminis_LightFromLit(float3 lit, float3 albedo) {{
    return Luminis_Luminance(max(lit, 0.0)) / max(Luminis_Luminance(albedo), 0.02);
}}
float3 Luminis_Finish(float3 lit, LuminisInput li) {{
    LuminisOutput lo = Luminis_Evaluate(li);
    float3 o = lit + lo.emissive;
    if (lo.debugActive) o = lo.debugColor;
    return o;
}}
"""

IRIS_STUB = COMMON_HEADER + r"""
cbuffer cbCommon  : register(b{com}) {{ float4 g_CommonParameter[4]; }}
Texture2D<float4> g_GBuffer2       : register(t{gb2});
SamplerState      g_SamplerGBuffer : register(s{sgb});

cbuffer cbPbrClock : register(b{pbr}) {{ float4 g_PbrParameterCommon[1]; }}
Texture2D<float4> g_Luminis        : register(t{lum});
Texture2D<float4> g_Luminis2       : register(t{lum2});
#define LUMINIS_LAYER2 (layer2 * Luminis_LayerValid(g_Luminis2))
#define LUMINIS_ANIMATE 1.0

float4 main(float4 pos : SV_Position, float4 litColor : LUMINIS0, float4 cap : LUMINIS1, float4 layer : LUMINIS2, float4 layer2 : LUMINIS3) : SV_Target0
{{
    float2 uv = pos.xy * g_CommonParameter[0].xy + g_CommonParameter[0].zw;
    float3 gb = g_GBuffer2.Sample(g_SamplerGBuffer, uv).xyz;
    float3 dc = g_MaterialParameter[0].xyz;
    float3 albedo = gb * gb * dc * dc;

    LuminisInput li;
    li.tint             = LUMINIS_P0.rgb;
    li.albedo           = albedo;
    // Glow area (g_LuminisMisc.z):
    //   0 = natural iris: the eye mask's blue channel, the game's own iris marker (default)
    //   1 = glow layer: PNG-style texture in g_SamplerLuminis (RGB = glow colors, alpha = where it glows)
    //   2 = painted eye mask: the eye mask's alpha
    //   3 = whole eye
    //   4 = emissive mask: the eye mask's red channel, where the game's own eye glow (g_EmissiveColor)
    //       shows; "glow editable" eye mods paint their glowing design there
    float area = round(g_MaterialParameter[28].z);
    bool useLayer = abs(area - 1.0) < 0.5;
    // Emissive mask uses the game's own eye-glow brightness curve: the glow rises steeply with the
    // brightness of the eye's color texture (x1 dark .. x10 bright in vanilla), so a mod's design pops.
    float emissiveCurve = (saturate(3.5714286 * (Luminis_Luminance(albedo) - 0.02)) * 9.0 + 1.0) / 10.0;
    // Unknown (newer) glow areas fall back to no glow, never to the whole eye.
    li.glowMask         = area < 0.5 ? cap.z : (useLayer ? layer.w * Luminis_LayerValid(g_Luminis)
                        : (area < 2.5 ? cap.x : (area < 3.5 ? 1.0 : (area < 4.5 ? cap.w * emissiveCurve : 0.0))));
    li.glowColor        = useLayer ? layer.rgb * layer.rgb : Luminis_HueToRGB(cap.y);
    li.rainbowHue       = cap.y;
    li.pixelSensitivity = 1.0;
    li.lightDiffuse     = Luminis_LightFromLit(litColor.xyz, albedo).xxx;
    li.ambient          = Luminis_Area();
    li.time             = g_PbrParameterCommon[0].x;
    li.layer2           = LUMINIS_LAYER2;
    li.animate          = LUMINIS_ANIMATE;
    return float4(Luminis_Finish(litColor.xyz, li), litColor.w);
}}
"""

HAIR_STUB = COMMON_HEADER + r"""
cbuffer cbPbr    : register(b{pbr}) {{ float4 g_PbrParameterCommon[5]; }}
cbuffer cbCustom : register(b{cus}) {{ float4 g_CustomizeParameter[7]; }}
Texture2D<float4> g_HairNormal    : register(t{nrm});
Texture2D<float4> g_HairMask      : register(t{msk});
Texture2D<float4> g_Luminis       : register(t{lum});
Texture2D<float4> g_Luminis2      : register(t{lum2});
#define LUMINIS_LAYER2 (g_Luminis2.SampleBias(g_SamplerNormal, uv.xy, bias) * Luminis_LayerValid(g_Luminis2))
#define LUMINIS_ANIMATE 1.0
SamplerState      g_SamplerNormal : register(s{smp});

float4 main(float4 pos : SV_Position, float4 col : COLOR0, float4 uv : TEXCOORD0, float4 litColor : LUMINIS0) : SV_Target0
{{
    // Hair color exactly as the shader builds it: main color blended to the highlight color by the
    // normal map's blue (second UV set), darkened by the mask's alpha, times vertex color and g_DiffuseColor.
    float bias = g_PbrParameterCommon[0].w + g_MaterialParameter[16].x;
    float highlight = saturate((g_HairNormal.SampleBias(g_SamplerNormal, uv.zw, bias).z - 0.015) * 1.01522839);
    float shade = g_HairMask.SampleBias(g_SamplerNormal, uv.xy, bias).w;
    float3 hair = lerp(g_CustomizeParameter[2].xyz, g_CustomizeParameter[3].xyz, highlight);
    float3 dc = g_MaterialParameter[0].xyz;
    float3 albedo = hair * (shade * shade) * col.xyz * dc * dc;

    // Glow area (g_LuminisMisc.z): 0 whole hair, 1 highlights only, 2 main color only, 3 glow layer (g_SamplerLuminis) alpha.
    float4 lum = g_Luminis.SampleBias(g_SamplerNormal, uv.xy, bias);
    float area = round(g_MaterialParameter[28].z);
    float mask = area < 0.5 ? 1.0 : (area < 1.5 ? highlight : (area < 2.5 ? 1.0 - highlight
               : (area < 3.5 ? lum.w * Luminis_LayerValid(g_Luminis) : 0.0)));   // unknown areas: no glow

    LuminisInput li;
    // Highlight glow color (g_LuminisHighlight): when switched on (w), highlight streaks use their own tint.
    li.tint             = lerp(LUMINIS_P0.rgb, LUMINIS_P4.rgb, highlight * saturate(LUMINIS_P4.w));
    li.albedo           = albedo;
    li.glowMask         = mask;
    li.glowColor        = lum.rgb * lum.rgb;   // Luminis texture RGB, approximately linear
    li.rainbowHue       = uv.y * g_MaterialParameter[29].z + g_MaterialParameter[29].w;  // along the strands
    li.pixelSensitivity = 1.0;
    li.lightDiffuse     = Luminis_LightFromLit(litColor.xyz, albedo).xxx;
    li.ambient          = Luminis_Area();
    li.time             = g_PbrParameterCommon[0].x;
    li.layer2           = LUMINIS_LAYER2;
    li.animate          = LUMINIS_ANIMATE;
    return float4(Luminis_Finish(litColor.xyz, li), litColor.w);
}}
"""

SKIN_STUB = COMMON_HEADER + r"""
cbuffer cbCommon : register(b{com}) {{ float4 g_CommonParameter[4]; }}
cbuffer cbPbr    : register(b{pbr}) {{ float4 g_PbrParameterCommon[5]; }}
Texture2D<float4> g_GBuffer2       : register(t{gb2});
Texture2D<float4> g_Luminis        : register(t{lum});
Texture2D<float4> g_Luminis2       : register(t{lum2});
#define LUMINIS_LAYER2 (g_Luminis2.SampleBias(g_SamplerNormal, uv.xy, bias) * Luminis_LayerValid(g_Luminis2))
#define LUMINIS_ANIMATE 1.0
SamplerState      g_SamplerGBuffer : register(s{sgb});
SamplerState      g_SamplerNormal  : register(s{smp});

float4 main(float4 pos : SV_Position, float4 uv : TEXCOORD0, float4 litColor : LUMINIS0) : SV_Target0
{{
    // Skin color as the G-buffer stores it (skin tone, tattoos and decals already blended in).
    float2 suv = pos.xy * g_CommonParameter[0].xy + g_CommonParameter[0].zw;
    float3 gb = g_GBuffer2.Sample(g_SamplerGBuffer, suv).xyz;
    float3 dc = g_MaterialParameter[0].xyz;
    float3 albedo = gb * gb * dc * dc;

    // Glow layer: the material's Luminis texture (g_SamplerLuminis). Its RGB are the glow colors,
    // its alpha (transparency) says where it glows.
    // Glow area (g_LuminisMisc.z): 0 = glow layer, 1 = whole skin.
    float bias = g_PbrParameterCommon[0].w + g_MaterialParameter[16].x;
    float4 layer = g_Luminis.SampleBias(g_SamplerNormal, uv.xy, bias);
    float area = round(g_MaterialParameter[28].z);
    float mask = area < 0.5 ? layer.w * Luminis_LayerValid(g_Luminis) : (area < 1.5 ? 1.0 : 0.0);   // unknown areas: no glow

    LuminisInput li;
    li.tint             = LUMINIS_P0.rgb;
    li.albedo           = albedo;
    li.glowMask         = mask;
    li.glowColor        = layer.rgb * layer.rgb;   // glow layer colors, approximately linear
    li.rainbowHue       = uv.y * g_MaterialParameter[29].z + g_MaterialParameter[29].w;
    li.pixelSensitivity = 1.0;
    li.lightDiffuse     = Luminis_LightFromLit(litColor.xyz, albedo).xxx;
    li.ambient          = Luminis_Area();
    li.time             = g_PbrParameterCommon[0].x;
    li.layer2           = LUMINIS_LAYER2;
    li.animate          = LUMINIS_ANIMATE;
    return float4(Luminis_Finish(litColor.xyz, li), litColor.w);
}}
"""

GEAR_STUB = COMMON_HEADER + r"""
cbuffer cbPbr    : register(b{pbr}) {{ float4 g_PbrParameterCommon[5]; }}
cbuffer cbCommon : register(b{com}) {{ float4 g_CommonParameter[4]; }}
Texture2D<float4> g_Luminis       : register(t{lum});
Texture2D<float4> g_Luminis2      : register(t{lum2});
SamplerState      g_SamplerNormal : register(s{smp});
#define HAS_DIFFUSE {has_dif}
#define HAS_LIGHT   {has_light}
#if HAS_DIFFUSE
Texture2D<float4> g_GearDiffuse   : register(t{dif});
#endif
#if HAS_LIGHT
Texture2D<float4> g_LightDiffuse  : register(t{ldif});
SamplerState      g_SamplerGBuffer : register(s{sgb});
#endif
#define HAS_INDEX   {has_idx}
#if HAS_INDEX
Texture2D<float4> g_GearIndex     : register(t{idx});
SamplerState      g_SamplerIndex  : register(s{idxs});
#endif
#define LUMINIS_LAYER2 (g_Luminis2.SampleBias(g_SamplerNormal, uv.xy, bias) * Luminis_LayerValid(g_Luminis2))
#define LUMINIS_ANIMATE rowAnimate

float4 main(float4 pos : SV_Position, float4 uv : TEXCOORD0, float4 litColor : LUMINIS0, float4 emis : LUMINIS1) : SV_Target0
{{
    float bias = g_PbrParameterCommon[0].w + g_MaterialParameter[16].x;
    float3 dc = g_MaterialParameter[0].xyz;
#if HAS_DIFFUSE
    float3 tex = g_GearDiffuse.SampleBias(g_SamplerNormal, uv.xy, bias).xyz;
    float3 albedo = tex * tex * dc * dc;            // the item's color texture (dye colors not included)
#else
    float3 albedo = float3(0.5, 0.5, 0.5) * dc * dc; // no color texture: colors come from the dye table
#endif

    // Glow area (g_LuminisMisc.z): 0 = glow layer (g_SamplerLuminis), 1 = whole item,
    // 2 = color table emissive: each color table row's Emissive Color decides where it glows and in
    // which color (the game's own row glow is switched off in this mode).
    float4 lum = g_Luminis.SampleBias(g_SamplerNormal, uv.xy, bias);
    float area = round(g_MaterialParameter[28].z);
    float emisMax = max(max(emis.x, emis.y), emis.z);

    // Per color table row (g_LuminisRows1..4, one value per row): 0 = animated, 1 = static, 2 = off.
    // The row comes from the index texture exactly as the game computes it.
#if HAS_INDEX
    float rowIdx = g_GearIndex.SampleLevel(g_SamplerIndex, uv.xy, 0).x;
    int row = clamp((int)((rowIdx * 255.0 + 8.0) * 0.0588235296), 0, 15);
#else
    int row = 0;
#endif
    // Select the row's setting with comparisons only (no runtime indexing, which would compile to an
    // indexed array the splicer can't handle).
    float rq = (float)(row >> 2);
    float rc = (float)(row & 3);
    float4 rowSet = rq < 0.5 ? g_MaterialParameter[LUMINIS_ROWS_BASE]
                  : rq < 1.5 ? g_MaterialParameter[LUMINIS_ROWS_BASE + 1]
                  : rq < 2.5 ? g_MaterialParameter[LUMINIS_ROWS_BASE + 2]
                             : g_MaterialParameter[LUMINIS_ROWS_BASE + 3];
    float rowSel = rc < 0.5 ? rowSet.x : rc < 1.5 ? rowSet.y : rc < 2.5 ? rowSet.z : rowSet.w;
    float rowAnimate = rowSel < 0.5 ? 1.0 : 0.0;
    float rowOn = rowSel < 1.5 ? 1.0 : 0.0;

    LuminisInput li;
    li.tint             = LUMINIS_P0.rgb;
    li.albedo           = albedo;
    li.glowMask         = (area < 0.5 ? lum.w * Luminis_LayerValid(g_Luminis) : (area < 1.5 ? 1.0
                        : (area < 2.5 ? saturate(emisMax) : 0.0))) * rowOn;   // unknown areas: no glow
    li.glowColor        = area < 1.5 ? lum.rgb * lum.rgb : emis.xyz / max(emisMax, 0.0001);
    li.rainbowHue       = uv.y * g_MaterialParameter[29].z + g_MaterialParameter[29].w;
    li.pixelSensitivity = 1.0;
#if HAS_LIGHT
    // Deferred lighting: read the light hitting this pixel straight from the light buffer.
    float2 suv = pos.xy * g_CommonParameter[0].xy + g_CommonParameter[0].zw;
    li.lightDiffuse     = g_LightDiffuse.Sample(g_SamplerGBuffer, suv).xyz;
#else
    li.lightDiffuse     = Luminis_LightFromLit(litColor.xyz, albedo).xxx;
#endif
    li.ambient          = Luminis_Area();
    li.time             = g_PbrParameterCommon[0].x;
    li.layer2           = LUMINIS_LAYER2;
    li.animate          = LUMINIS_ANIMATE;
    return float4(Luminis_Finish(litColor.xyz, li), litColor.w);
}}
"""

# Registers to rename: also inside brackets (cb0[r4.x + 41]), so runtime indexing reads the right register.
REG = re.compile(r"(?<![A-Za-z0-9_])([rvo])(\d+)(?=[.\s,\]|)+]|$)")

class Skip(Exception):
    pass

def run(args, cwd=None):
    r = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stdout + r.stderr).strip())
    return r.stdout + r.stderr

def bindings(text):
    b = {}
    for m in re.finditer(r"^// (\S+)\s+(sampler|texture|cbuffer)\s+\S+\s+\S+\s+(\d+)\s+\d+", text, re.M):
        b[m.group(1)] = (m.group(2), int(m.group(3)))
    return b

def signature(text, title):
    sig, inside = {}, False
    for l in text.splitlines():
        if l.startswith(f"// {title} signature"):
            inside = True; continue
        if inside and re.match(r"// \w+ signature", l):
            break
        m = re.match(r"//\s+(\w+)\s+(\d+)\s+\w+\s+(\d+)\s", l)
        if inside and m:
            sig[(m.group(1).upper(), int(m.group(2)))] = int(m.group(3))
    return sig

def need(b, name, kind):
    if name not in b or b[name][0] != kind:
        raise Skip(f"doesn't bind {name} ({kind})")
    return b[name][1]

DYNAMIC_CBS = set()   # constant buffers the current epilogue indexes at runtime

def parse_stub(listing):
    DYNAMIC_CBS.clear()
    body, temps, cbs, started = [], 0, {}, False
    for l in listing.splitlines():
        s = l.strip()
        if not s or s.startswith("//"):
            continue
        if s.startswith("ps_5_0"):
            started = True; continue
        if not started:
            continue
        if s.startswith(("dcl_immediateConstantBuffer", "dcl_indexableTemp")):
            raise Skip("epilogue uses arrays; can't splice")
        if s.startswith("dcl_temps"):
            temps = int(s.split()[1]); continue
        m = re.match(r"dcl_constantbuffer [cC][bB](\d+)\[(\d+)\]", s)
        if m:
            cbs[int(m.group(1))] = int(m.group(2))
            if "dynamicIndexed" in s:
                DYNAMIC_CBS.add(int(m.group(1)))
            continue
        if s.startswith("dcl_"):
            continue
        body.append(s)
    if not body or body[-1] != "ret":
        raise Skip("unexpected fxc listing (no final ret)")
    body = body[:-1]
    if any(x == "ret" or x.startswith(("ret ", "discard")) for x in body):
        raise Skip("epilogue has an early return; can't splice")
    return body, temps, cbs, signature(listing, "Input")

def patch_one(profile, n, out_dir, work_root):
    work = work_root / f"ps_{n}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    src = ROOT / "blobs" / profile / "all" / f"ps_{n}.dxbc"
    if not src.exists():
        raise Skip(f"{src} not found (run shpk_extract.py first)")
    shutil.copy2(src, work / src.name)
    run([DECOMPILER, "-d", src.name], work)
    asm_path = work / f"ps_{n}.asm"
    text = asm_path.read_text()
    b = bindings(text)
    orig_sig = signature(text, "Input")
    if need(b, "g_MaterialParameter", "cbuffer") != 0:
        raise Skip("g_MaterialParameter isn't in register b0")
    amb_b = need(b, "g_AmbientParam", "cbuffer")
    inst_b = need(b, "g_InstanceParameter", "cbuffer")
    tex_slots = [v[1] for v in b.values() if v[0] == "texture"]
    lines = text.splitlines()
    temps_i = [i for i, l in enumerate(lines) if l.startswith("dcl_temps ")]
    if len(temps_i) != 1:
        raise Skip("couldn't find dcl_temps")
    base = int(lines[temps_i[0]].split()[1])
    lit_reg, cap_reg, layer_reg, layer2_reg = f"r{base}", f"r{base + 1}", f"r{base + 2}", f"r{base + 3}"
    first_stub_reg = base + 4

    # Final color: the multiply by g_InstanceParameter.m_MulColor (cb[0]) right before output.
    mul_re = re.compile(rf"(\s*)mul (r\d+)\.xyz, (?:(r\d+\.\w+), cb{inst_b}\[0\]\.xyzx|cb{inst_b}\[0\]\.xyzx, (r\d+\.\w+))\s*$")
    mul_i = [i for i, l in enumerate(lines) if mul_re.match(l)]
    if len(mul_i) != 1:
        raise Skip(f"expected one final color multiply, found {len(mul_i)}")
    mm = mul_re.match(lines[mul_i[0]])
    ind, dst, srcop = mm.group(1), mm.group(2), mm.group(3) or mm.group(4)

    inserts_before_mask, extra_tex = [], None
    if profile == "iris":
        mask_t = need(b, "g_SamplerMask.T", "texture")
        gb2_t = need(b, "g_SamplerGBuffer2", "texture")
        sgb_s = need(b, "g_SamplerGBuffer.S", "sampler")
        com_b = need(b, "g_CommonParameter", "cbuffer")
        tex_t = b["g_SamplerDiffuse.T"][1] if "g_SamplerDiffuse.T" in b else max(tex_slots) + 1
        lum_t = max(max(tex_slots), tex_t) + 1
        mask_i = [i for i, l in enumerate(lines) if re.match(r"\s*sample", l) and re.search(rf",\s*t{mask_t}\.", l)]
        if len(mask_i) != 1:
            raise Skip(f"expected one sample of the mask texture, found {len(mask_i)}")
        m = re.match(r"(\s*)(\S+)\s+(.*)$", lines[mask_i[0]])
        mind, op, operands = m.group(1), m.group(2), [x.strip() for x in m.group(3).split(",")]
        if len(operands) not in (4, 5) or not re.match(rf"t{mask_t}\.", operands[2]):
            raise Skip(f"mask sample has an unexpected form: {lines[mask_i[0]].strip()}")
        samp_slot = int(operands[3][1:])
        tail = (", " + operands[4]) if len(operands) == 5 else ""
        inserts_before_mask = [mask_i[0], [
            "// ---- Luminis capture: painted mask (x), glow hue (y), iris marker (z), emissive mask (w), glow layers 1 and 2 ----",
            f"{mind}{op} {cap_reg}.x, {operands[1]}, t{mask_t}.wwww, {operands[3]}{tail}",
            f"{mind}{op} {cap_reg}.y, {operands[1]}, t{tex_t}.wwww, {operands[3]}{tail}",
            f"{mind}{op} {cap_reg}.z, {operands[1]}, t{mask_t}.zzzz, {operands[3]}{tail}",
            f"{mind}{op} {cap_reg}.w, {operands[1]}, t{mask_t}.xxxx, {operands[3]}{tail}",
            f"{mind}{op} {layer_reg}.xyzw, {operands[1]}, t{lum_t}.xyzw, {operands[3]}{tail}",
            f"{mind}{op} {layer2_reg}.xyzw, {operands[1]}, t{lum_t + 1}.xyzw, {operands[3]}{tail}"]]
        extra_tex = [("g_SamplerDiffuse", tex_t, samp_slot, "g_SamplerDiffuse.T" not in b),
                     ("g_SamplerLuminis", lum_t, samp_slot, True),
                     ("g_SamplerLuminis2", lum_t + 1, samp_slot, True)]
        pbr_b = need(b, "g_PbrParameterCommon", "cbuffer")
        stub_src = IRIS_STUB.format(regs=MATERIAL_REGS, amb=amb_b, com=com_b, gb2=gb2_t, sgb=sgb_s, pbr=pbr_b,
                                    lum=lum_t, lum2=lum_t + 1)
    elif profile == "hair":
        nrm_t = need(b, "g_SamplerNormal.T", "texture")
        msk_t = need(b, "g_SamplerMask.T", "texture")
        smp_s = need(b, "g_SamplerNormal.S", "sampler")
        pbr_b = need(b, "g_PbrParameterCommon", "cbuffer")
        cus_b = need(b, "g_CustomizeParameter", "cbuffer")
        lum_t = max(tex_slots) + 1
        for key in [("COLOR", 0), ("TEXCOORD", 0)]:
            if key not in orig_sig:
                raise Skip(f"input {key} not in the shader's signature")
        extra_tex = [("g_SamplerLuminis", lum_t, smp_s, True), ("g_SamplerLuminis2", lum_t + 1, smp_s, True)]
        stub_src = HAIR_STUB.format(regs=MATERIAL_REGS, amb=amb_b, pbr=pbr_b, cus=cus_b,
                                    nrm=nrm_t, msk=msk_t, lum=lum_t, lum2=lum_t + 1, smp=smp_s)
    elif profile == "skin":
        gb2_t = need(b, "g_SamplerGBuffer2", "texture")
        sgb_s = need(b, "g_SamplerGBuffer.S", "sampler")
        smp_s = need(b, "g_SamplerNormal.S", "sampler")
        com_b = need(b, "g_CommonParameter", "cbuffer")
        pbr_b = need(b, "g_PbrParameterCommon", "cbuffer")
        lum_t = max(tex_slots) + 1
        if ("TEXCOORD", 0) not in orig_sig:
            raise Skip("input TEXCOORD0 not in the shader's signature")
        extra_tex = [("g_SamplerLuminis", lum_t, smp_s, True), ("g_SamplerLuminis2", lum_t + 1, smp_s, True)]
        stub_src = SKIN_STUB.format(regs=MATERIAL_REGS, amb=amb_b, com=com_b, pbr=pbr_b,
                                    gb2=gb2_t, lum=lum_t, lum2=lum_t + 1, sgb=sgb_s, smp=smp_s)
    elif profile in ("characterlegacy", "character"):
        smp_s = need(b, "g_SamplerNormal.S", "sampler")
        pbr_b = need(b, "g_PbrParameterCommon", "cbuffer")
        com_b = need(b, "g_CommonParameter", "cbuffer")
        if ("TEXCOORD", 0) not in orig_sig:
            raise Skip("input TEXCOORD0 not in the shader's signature")
        has_dif = "g_SamplerDiffuse.T" in b
        has_light = "g_SamplerLightDiffuse" in b and "g_SamplerGBuffer.S" in b
        has_idx = "g_SamplerIndex.T" in b and "g_SamplerIndex.S" in b
        # Color table emissive: the row emissive is multiplied by g_MaterialParameterDynamic.m_EmissiveColor
        # exactly once. Copy it for Luminis first; afterwards, zero the game's own result when Glow area is
        # 2 (color table emissive), so Luminis takes over the row glow.
        emi_lines = None
        if "g_MaterialParameterDynamic" in b and b["g_MaterialParameterDynamic"][0] == "cbuffer":
            dyn = b["g_MaterialParameterDynamic"][1]
            emi_re = re.compile(rf"(\s*)mul (r\d+)\.xyz, (?:(r\d+\.\w+), cb{dyn}\[0\]\.xyzx|cb{dyn}\[0\]\.xyzx, (r\d+\.\w+))\s*$")
            emi_i = [i for i, l in enumerate(lines) if emi_re.match(l)]
            if len(emi_i) == 1 and emi_i[0] < mul_i[0]:
                em = emi_re.match(lines[emi_i[0]])
                eind, edst, esrc = em.group(1), em.group(2), em.group(3) or em.group(4)
                emi_lines = (emi_i[0], [
                    "// ---- Luminis capture: color table emissive ----",
                    f"{eind}mov {cap_reg}.xyz, {esrc}",
                    lines[emi_i[0]],
                    f"{eind}eq {cap_reg}.w, cb0[28].z, l(2.000000)",
                    f"{eind}movc {edst}.xyz, {cap_reg}.wwww, l(0,0,0,0), {edst}.xyzx"])
        lum_t = max(tex_slots) + 1
        extra_tex = [("g_SamplerLuminis", lum_t, smp_s, True), ("g_SamplerLuminis2", lum_t + 1, smp_s, True)]
        stub_src = GEAR_STUB.format(regs=MATERIAL_REGS, amb=amb_b, pbr=pbr_b, com=com_b, lum=lum_t, lum2=lum_t + 1,
                                    smp=smp_s, has_dif=int(has_dif), has_light=int(has_light),
                                    dif=b["g_SamplerDiffuse.T"][1] if has_dif else 0,
                                    ldif=b["g_SamplerLightDiffuse"][1] if has_light else 0,
                                    sgb=b["g_SamplerGBuffer.S"][1] if has_light else 0,
                                    has_idx=int(has_idx), idx=b["g_SamplerIndex.T"][1] if has_idx else 0,
                                    idxs=b["g_SamplerIndex.S"][1] if has_idx else 0)
    else:
        raise Skip(f"unknown profile {profile}")

    stub = work / "epilogue.hlsl"
    stub.write_text(f"// Luminis epilogue, {profile} pixel shader #{n} (generated)\n" + stub_src)
    run(["fxc", "/nologo", "/T", "ps_5_0", "/E", "main", "/O3", "/I", INCLUDE,
         "/Fc", work / "epilogue.asm", "/Fo", work / "epilogue.dxbc", stub])
    body, stub_temps, stub_cbs, stub_sig = parse_stub((work / "epilogue.asm").read_text())

    vmap = {}
    for key, reg in stub_sig.items():
        if key == ("LUMINIS", 0):
            vmap[reg] = lit_reg
        elif key == ("LUMINIS", 1):
            vmap[reg] = cap_reg
        elif key == ("LUMINIS", 2):
            vmap[reg] = layer_reg
        elif key == ("LUMINIS", 3):
            vmap[reg] = layer2_reg
        elif key in orig_sig:
            vmap[reg] = f"v{orig_sig[key]}"
        else:
            raise Skip(f"epilogue input {key} has no match in the shader")

    def remap(instr):
        def sub(m):
            kind, idx = m.group(1), int(m.group(2))
            if kind == "r":
                return f"r{first_stub_reg + idx}"
            if kind == "o":
                if idx != 0:
                    raise Skip("epilogue writes an unexpected output")
                return lit_reg
            if idx not in vmap:
                raise Skip(f"epilogue reads unexpected input v{idx}")
            return vmap[idx]
        return REG.sub(sub, instr)

    epilogue = (["// ---- Luminis epilogue begin ----", f"{ind}mov {lit_reg}.xyz, {srcop}"]
                + [ind + remap(x) for x in body]
                + ["// ---- Luminis epilogue end ----"])
    out = list(lines)
    out[mul_i[0]] = f"{ind}mul {dst}.xyz, {lit_reg}.xyzx, cb{inst_b}[0].xyzx"
    out[mul_i[0]:mul_i[0]] = epilogue
    if inserts_before_mask:
        idx, ins = inserts_before_mask
        out[idx:idx] = ins
    if profile in ("characterlegacy", "character"):
        if emi_lines:
            idx, ins = emi_lines
            out[idx:idx + 1] = ins
        else:   # no row emissive in this variant: feed Luminis zeros
            out[mul_i[0]:mul_i[0]] = [f"{ind}mov {cap_reg}.xyzw, l(0,0,0,0)"]
    out[temps_i[0]] = f"dcl_temps {first_stub_reg + stub_temps}"
    # Make sure every constant buffer is declared large enough for the epilogue.
    for cb, size in stub_cbs.items():
        if cb == 0:
            size = max(size, MATERIAL_REGS)
        found = False
        for i, l in enumerate(out):
            m = re.match(rf"(dcl_constantbuffer [cC][bB]{cb}\[)(\d+)(\].*)", l)
            if m:
                found = True
                if int(m.group(2)) < size:
                    out[i] = f"{m.group(1)}{size}{m.group(3)}"
                if cb in DYNAMIC_CBS:   # the epilogue indexes this buffer at runtime
                    out[i] = out[i].replace("immediateIndexed", "dynamicIndexed")
        if not found:
            raise Skip(f"epilogue uses cb{cb}, which the shader doesn't declare")
    for name, slot, samp, add in extra_tex:
        if add:
            res = [i for i, l in enumerate(out) if l.startswith("dcl_resource")]
            out.insert(res[-1] + 1, f"dcl_resource_texture2d (float,float,float,float) t{slot}")
    asm_path.write_text("\n".join(out) + "\n")

    for old in work.glob("*.shdr"):   # so the assembler's output is the only .shdr afterwards
        old.unlink()
    run([DECOMPILER, "-a", "--copy-reflection", src, asm_path.name], work)
    produced = list(work.glob("*.shdr"))
    if len(produced) != 1:
        raise Skip("couldn't find the assembled output")
    shutil.copy2(produced[0], out_dir / f"ps_{n}.dxbc")
    bindings_out = []
    for name, slot, samp, add in extra_tex:
        samp_name = next((k[:-2] for k, v in b.items() if v == ("sampler", samp) and k.endswith(".S")), None)
        if not samp_name:
            raise Skip(f"couldn't name sampler s{samp}")
        bindings_out.append({"ps": n, "texture": name, "slot": slot, "sampler": samp_name, "add_binding": add,
                             "epilogue_instructions": len(body)})
    return bindings_out

def main():
    if len(sys.argv) < 4:
        sys.exit("usage: python tools\\luminis_asm.py iris|hair|skin|characterlegacy|character OUT_DIR INDEX [INDEX ...]")
    profile = sys.argv[1]
    out_dir = pathlib.Path(sys.argv[2]).resolve()
    indices = [int(x) for x in sys.argv[3:]]
    out_dir.mkdir(parents=True, exist_ok=True)
    results, skipped = [], []
    for n in indices:
        try:
            rs = patch_one(profile, n, out_dir, out_dir / "_work")
            results.extend(rs)
            print(f"ok    ps_{n}  (epilogue {rs[0]['epilogue_instructions']} instructions, extra texture "
                  f"{', '.join('t%d' % r['slot'] for r in rs)})   [{indices.index(n) + 1}/{len(indices)}]", flush=True)
        except Skip as e:
            skipped.append(n); print(f"SKIP  ps_{n}: {e}", flush=True)
        except Exception as e:
            skipped.append(n); print(f"FAIL  ps_{n}: {e}", flush=True)
    (out_dir / "bindings.json").write_text(json.dumps(results, indent=2))
    print(f"\n{len({r['ps'] for r in results})} built, {len(skipped)} skipped or failed{': ' + str(skipped) if skipped else ''}")
    sys.exit(0 if results else 1)

if __name__ == "__main__":
    main()
