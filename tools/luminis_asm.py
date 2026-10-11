# luminis_asm.py - build Luminis versions of composite pixel shaders by patching their assembly.
#
# Usage (from D:\luminis):
#   python tools\luminis_asm.py PROFILE OUT_DIR INDEX [INDEX ...]
#
#   PROFILE  iris, hair or skin
#
# For each pixel shader index it disassembles blobs\<profile>\all\ps_<N>.dxbc, compiles a small
# HLSL "epilogue" (include\luminis_glow.hlsli plus profile-specific setup) with fxc for this
# shader's registers, splices it in just before the final color is written, and reassembles
# with the original signatures. Shaders that don't fit are reported and skipped.
# Writes OUT_DIR\ps_<N>.dxbc and OUT_DIR\bindings.json (the extra texture binding each needs).
import json, pathlib, re, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
DECOMPILER = ROOT / "tools" / "3dmigoto" / "cmd_Decompiler.exe"
INCLUDE = ROOT / "include"
MATERIAL_REGS = 31  # g_MaterialParameter size including the Luminis slots 26..30

COMMON_HEADER = r"""
cbuffer cbMat     : register(b0)     {{ float4 g_MaterialParameter[{regs}]; }}
cbuffer cbAmbient : register(b{amb}) {{ float4 g_AmbientParam[10]; }}
#define LUMINIS_P0 g_MaterialParameter[26]
#define LUMINIS_P1 g_MaterialParameter[27]
#define LUMINIS_P2 g_MaterialParameter[28]
#define LUMINIS_P3 g_MaterialParameter[29]
#define LUMINIS_P4 g_MaterialParameter[30]
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

float4 main(float4 pos : SV_Position, float4 litColor : LUMINIS0, float4 cap : LUMINIS1) : SV_Target0
{{
    float2 uv = pos.xy * g_CommonParameter[0].xy + g_CommonParameter[0].zw;
    float3 gb = g_GBuffer2.Sample(g_SamplerGBuffer, uv).xyz;
    float3 dc = g_MaterialParameter[0].xyz;
    float3 albedo = gb * gb * dc * dc;

    LuminisInput li;
    li.tint             = LUMINIS_P0.rgb;
    li.albedo           = albedo;
    li.glowMask         = cap.x;                     // eye mask alpha
    li.glowColor        = Luminis_HueToRGB(cap.y);   // hue painted in the eye color texture alpha
    li.rainbowHue       = cap.y;
    li.pixelSensitivity = 1.0;
    li.lightDiffuse     = Luminis_LightFromLit(litColor.xyz, albedo).xxx;
    li.ambient          = Luminis_Area();
    return float4(Luminis_Finish(litColor.xyz, li), litColor.w);
}}
"""

HAIR_STUB = COMMON_HEADER + r"""
cbuffer cbPbr    : register(b{pbr}) {{ float4 g_PbrParameterCommon[5]; }}
cbuffer cbCustom : register(b{cus}) {{ float4 g_CustomizeParameter[7]; }}
Texture2D<float4> g_HairNormal    : register(t{nrm});
Texture2D<float4> g_HairMask      : register(t{msk});
Texture2D<float4> g_Luminis       : register(t{lum});
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

    // Glow area (g_LuminisMisc.z): 0 whole hair, 1 highlights only, 2 main color only, 3 Luminis texture alpha.
    float4 lum = g_Luminis.SampleBias(g_SamplerNormal, uv.xy, bias);
    float area = round(g_MaterialParameter[28].z);
    float mask = area < 0.5 ? 1.0 : (area < 1.5 ? highlight : (area < 2.5 ? 1.0 - highlight : lum.w));

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
    return float4(Luminis_Finish(litColor.xyz, li), litColor.w);
}}
"""

SKIN_STUB = COMMON_HEADER + r"""
cbuffer cbCommon : register(b{com}) {{ float4 g_CommonParameter[4]; }}
cbuffer cbPbr    : register(b{pbr}) {{ float4 g_PbrParameterCommon[5]; }}
Texture2D<float4> g_GBuffer2       : register(t{gb2});
Texture2D<float4> g_Luminis        : register(t{lum});
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
    float mask = area < 0.5 ? layer.w : 1.0;

    LuminisInput li;
    li.tint             = LUMINIS_P0.rgb;
    li.albedo           = albedo;
    li.glowMask         = mask;
    li.glowColor        = layer.rgb * layer.rgb;   // glow layer colors, approximately linear
    li.rainbowHue       = uv.y * g_MaterialParameter[29].z + g_MaterialParameter[29].w;
    li.pixelSensitivity = 1.0;
    li.lightDiffuse     = Luminis_LightFromLit(litColor.xyz, albedo).xxx;
    li.ambient          = Luminis_Area();
    return float4(Luminis_Finish(litColor.xyz, li), litColor.w);
}}
"""

REG = re.compile(r"(?<![A-Za-z0-9_\[])([rvo])(\d+)(?=[.\s,\]|)]|$)")

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

def parse_stub(listing):
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
            cbs[int(m.group(1))] = int(m.group(2)); continue
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
    lit_reg, cap_reg, first_stub_reg = f"r{base}", f"r{base + 1}", base + 2

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
            "// ---- Luminis capture: glow mask (x) and glow hue (y) ----",
            f"{mind}{op} {cap_reg}.x, {operands[1]}, t{mask_t}.wwww, {operands[3]}{tail}",
            f"{mind}{op} {cap_reg}.y, {operands[1]}, t{tex_t}.wwww, {operands[3]}{tail}"]]
        extra_tex = ("g_SamplerDiffuse", tex_t, samp_slot, "g_SamplerDiffuse.T" not in b)
        stub_src = IRIS_STUB.format(regs=MATERIAL_REGS, amb=amb_b, com=com_b, gb2=gb2_t, sgb=sgb_s)
    elif profile == "hair":
        nrm_t = need(b, "g_SamplerNormal.T", "texture")
        msk_t = need(b, "g_SamplerMask.T", "texture")
        smp_s = need(b, "g_SamplerNormal.S", "sampler")
        pbr_b = need(b, "g_PbrParameterCommon", "cbuffer")
        cus_b = need(b, "g_CustomizeParameter", "cbuffer")
        lum_t = b["g_SamplerDecal.T"][1] if "g_SamplerDecal.T" in b else max(tex_slots) + 1
        for key in [("COLOR", 0), ("TEXCOORD", 0)]:
            if key not in orig_sig:
                raise Skip(f"input {key} not in the shader's signature")
        extra_tex = ("g_SamplerDecal", lum_t, smp_s, "g_SamplerDecal.T" not in b)
        stub_src = HAIR_STUB.format(regs=MATERIAL_REGS, amb=amb_b, pbr=pbr_b, cus=cus_b,
                                    nrm=nrm_t, msk=msk_t, lum=lum_t, smp=smp_s)
    elif profile == "skin":
        gb2_t = need(b, "g_SamplerGBuffer2", "texture")
        sgb_s = need(b, "g_SamplerGBuffer.S", "sampler")
        smp_s = need(b, "g_SamplerNormal.S", "sampler")
        com_b = need(b, "g_CommonParameter", "cbuffer")
        pbr_b = need(b, "g_PbrParameterCommon", "cbuffer")
        lum_t = max(tex_slots) + 1
        if ("TEXCOORD", 0) not in orig_sig:
            raise Skip("input TEXCOORD0 not in the shader's signature")
        extra_tex = ("g_SamplerLuminis", lum_t, smp_s, True)
        stub_src = SKIN_STUB.format(regs=MATERIAL_REGS, amb=amb_b, com=com_b, pbr=pbr_b,
                                    gb2=gb2_t, lum=lum_t, sgb=sgb_s, smp=smp_s)
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
        if not found:
            raise Skip(f"epilogue uses cb{cb}, which the shader doesn't declare")
    name, slot, samp, add = extra_tex
    if add:
        res = [i for i, l in enumerate(out) if l.startswith("dcl_resource")]
        out.insert(res[-1] + 1, f"dcl_resource_texture2d (float,float,float,float) t{slot}")
    asm_path.write_text("\n".join(out) + "\n")

    before = {p.name: p.stat().st_mtime for p in work.iterdir()}
    time.sleep(1.1)
    run([DECOMPILER, "-a", "--copy-reflection", src, asm_path.name], work)
    produced = [p for p in work.iterdir() if p.suffix == ".shdr" and (p.name not in before or p.stat().st_mtime > before[p.name])]
    if len(produced) != 1:
        raise Skip("couldn't find the assembled output")
    shutil.copy2(produced[0], out_dir / f"ps_{n}.dxbc")
    samp_name = next((k[:-2] for k, v in b.items() if v == ("sampler", samp) and k.endswith(".S")), None)
    if not samp_name:
        raise Skip(f"couldn't name sampler s{samp}")
    return {"ps": n, "texture": name, "slot": slot, "sampler": samp_name, "add_binding": add,
            "epilogue_instructions": len(body)}

def main():
    if len(sys.argv) < 4:
        sys.exit("usage: python tools\\luminis_asm.py iris|hair|skin OUT_DIR INDEX [INDEX ...]")
    profile = sys.argv[1]
    out_dir = pathlib.Path(sys.argv[2]).resolve()
    indices = [int(x) for x in sys.argv[3:]]
    out_dir.mkdir(parents=True, exist_ok=True)
    results, skipped = [], []
    for n in indices:
        try:
            r = patch_one(profile, n, out_dir, out_dir / "_work")
            results.append(r)
            print(f"ok    ps_{n}  (epilogue {r['epilogue_instructions']} instructions, extra texture t{r['slot']})"
                  f"   [{indices.index(n) + 1}/{len(indices)}]", flush=True)
        except Skip as e:
            skipped.append(n); print(f"SKIP  ps_{n}: {e}", flush=True)
        except Exception as e:
            skipped.append(n); print(f"FAIL  ps_{n}: {e}", flush=True)
    (out_dir / "bindings.json").write_text(json.dumps(results, indent=2))
    print(f"\n{len(results)} built, {len(skipped)} skipped or failed{': ' + str(skipped) if skipped else ''}")
    sys.exit(0 if results else 1)

if __name__ == "__main__":
    main()
