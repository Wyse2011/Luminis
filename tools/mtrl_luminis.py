# mtrl_luminis.py - add or update the Luminis glow settings in a material (.mtrl).
#
# Usage (from D:\luminis):
#   python tools\mtrl_luminis.py IN.mtrl OUT.mtrl [--color R,G,B,INTENSITY] [--light START,END,MODE,SENS]
#                                                 [--misc ALBEDO,AREA,PIXELSENS,DEBUG]
#
#   --color  tint red, green, blue, intensity          (default 1,1,1,1.5; skin materials 1,1,1,0)
#   --light  dark start, dark end, mode, sensitivity   (default 0.02,0.15,1,1)
#            mode: 0 = always on, 1 = glow in darkness, 2 = glow in light
#   --misc   color source, area mix, per-pixel sensitivity, debug view   (default 1,0.5,0,0)
#            color source: 0 = tint only, 1 = eye color, 2 = glow map (hue in color texture alpha)
#            debug: 0 = off, 1 = mask, 2 = light brightness, 3 = light gate, 4 = emissive only
#   --detail detail, detail gain, rainbow length, rainbow shift   (default 0,2,0,0)
#   --highlight R,G,B,ON   hair: glow color for the highlight streaks; ON = 1 to use it, 0 to
#            let highlights share the main tint   (default 1,1,1,0)
#   --anim MODE,SPEED,STEPS,SOFTNESS   animation: mode 0 off, 1 blink, 2 two-color, 3 color steps,
#            4 chroma; speed in cycles per clock unit; steps 2..12; softness 0 hard .. 1 smooth
#   --animcolor R,G,B,0   color 2 (two-color and custom colors); --animcolor3/--animcolor4 colors 3 and 4
#   --l2color R,G,B,INTENSITY / --l2light START,END,MODE,SENS / --l2anim MODE,SPEED,STEPS,SOFT
#            glow layer 2's own tint and intensity, light behavior and animation
#   --glow-texture2 GAME_PATH  attach glow layer 2 (g_SamplerLuminis2)
#   --glow-texture GAME_PATH   give the material a glow layer ("Luminis texture"): a texture whose
#            RGB are the glow colors and whose alpha (transparency) says where it glows.
#            Eyes, hair and skin all use the g_SamplerLuminis slot.
#            detail: 0 = flat glow, 1 = the surface's light/dark detail shows through the glow
#
# Settings the material doesn't have yet are added with defaults (or the values you pass);
# settings it already has are only changed if you pass that option.
# The material's shader package must be one patched with shpk_add_params.py.
import argparse, pathlib, struct, sys, zlib

def name_id(name):
    return zlib.crc32(name.encode(), 0xFFFFFFFF) ^ 0xFFFFFFFF

NAMES = {"color": "g_LuminisColor", "light": "g_LuminisLight", "misc": "g_LuminisMisc",
         "detail": "g_LuminisDetail", "highlight": "g_LuminisHighlight",
         "anim": "g_LuminisAnim", "animcolor": "g_LuminisAnimColor",
         "animcolor3": "g_LuminisAnimColor3", "animcolor4": "g_LuminisAnimColor4",
         "l2color": "g_LuminisL2Color", "l2light": "g_LuminisL2Light", "l2anim": "g_LuminisL2Anim",
         "l2animcolor": "g_LuminisL2AnimColor", "l2animcolor3": "g_LuminisL2AnimColor3",
         "l2animcolor4": "g_LuminisL2AnimColor4",
         "rows1": "g_LuminisRows1", "rows2": "g_LuminisRows2", "rows3": "g_LuminisRows3", "rows4": "g_LuminisRows4"}
DEFAULTS = {"color": (1, 1, 1, 1.5), "light": (0.02, 0.15, 1, 1), "misc": (1, 0.5, 0, 0),
            "detail": (0, 2, 1, 0), "highlight": (1, 1, 1, 0),
            "anim": (0, 1, 4, 1), "animcolor": (0, 0, 1, 0),
            "animcolor3": (0, 1, 0, 0.15), "animcolor4": (1, 1, 0, 1),
            "l2color": (1, 1, 1, 0), "l2light": (0.02, 0.15, 0, 1), "l2anim": (0, 1, 4, 1),
            "l2animcolor": (0, 0, 1, 2), "l2animcolor3": (0, 1, 0, 0.15), "l2animcolor4": (1, 1, 0, 1),
            "rows1": (0, 0, 0, 0), "rows2": (0, 0, 0, 0), "rows3": (0, 0, 0, 0), "rows4": (0, 0, 0, 0)}
# Per-shader overrides of the defaults. Skin materials start with intensity 0: body mods often
# ship color textures whose alpha is fully white, so a non-zero default would light up the whole
# body. Glow switches on when someone sets an intensity (and paints the tattoo mask).
SHADER_DEFAULTS = {"skin.shpk": {"color": (1, 1, 1, 0), "misc": (2, 0.5, 0, 0)},
                   # gear, minions, mounts: off until set up; glow layer colors by default
                   "characterlegacy.shpk": {"color": (1, 1, 1, 0), "misc": (2, 0.5, 0, 0)},
                   "character.shpk": {"color": (1, 1, 1, 0), "misc": (2, 0.5, 0, 0)}}
# Which texture slot holds the glow layer ("Luminis texture") for each shader.
GLOW_TEXTURE_SLOT = {k: "g_SamplerLuminis" for k in ("hair.shpk", "skin.shpk", "iris.shpk", "characterlegacy.shpk", "character.shpk")}

def fail(msg):
    sys.exit(f"STOPPED: {msg}\nNothing was written.")

def set_glow_texture(d, path, slot_name=None):
    """Add (or repoint) a texture bound to g_SamplerDecal. New strings are appended to the
    string table, so every existing string offset stays valid."""
    ver, fsize, dsize, ssize, shoff, tc, uvc, csc, addsz = struct.unpack_from("<IHHHHBBBB", d, 0)
    strings_at = 16 + 4 * (tc + uvc + csc)
    hdr = strings_at + ssize + addsz + dsize
    vsz, kc, cc, sc = struct.unpack_from("<HHHH", d, hdr)
    samps_at = hdr + 12 + 8 * kc + 8 * cc
    samplers = [struct.unpack_from("<IIB", d, samps_at + 12 * i) for i in range(sc)]
    shader = (shader_package_name(d) or "").lower()
    if shader not in GLOW_TEXTURE_SLOT:
        fail(f"{shader or 'this shader'} has no glow layer slot (supported: {', '.join(GLOW_TEXTURE_SLOT)})")
    DECAL_ID = name_id(slot_name or GLOW_TEXTURE_SLOT[shader])
    if not samplers:
        fail("material has no samplers to copy settings from")
    new_off = ssize
    blob = path.encode() + b"\0"
    blob += b"\0" * (-(ssize + len(blob)) % 4)
    existing = [s for s in samplers if s[0] == DECAL_ID]
    if existing:
        tex_i = existing[0][2]
        d = d[:strings_at + ssize] + blob + d[strings_at + ssize:]
        struct.pack_into("<H", d, 16 + 4 * tex_i, new_off)
        struct.pack_into("<H", d, 8, ssize + len(blob))
        struct.pack_into("<H", d, 4, len(d))
        print(f"glow texture repointed to {path}")
        return d
    if tc >= 255:
        fail("too many textures")
    # sampler first (later in the file), then strings, then the new texture entry (earliest)
    sampler = struct.pack("<IIB3x", DECAL_ID, samplers[0][1], tc)
    d = d[:samps_at + 12 * sc] + sampler + d[samps_at + 12 * sc:]
    struct.pack_into("<HHHH", d, hdr, vsz, kc, cc, sc + 1)
    d = d[:strings_at + ssize] + blob + d[strings_at + ssize:]
    entry_at = 16 + 4 * tc
    d = d[:entry_at] + struct.pack("<HH", new_off, 0) + d[entry_at:]
    struct.pack_into("<HHHHBBBB", d, 4, len(d), dsize, ssize + len(blob), shoff, tc + 1, uvc, csc, addsz)
    print(f"glow texture added: {path}")
    return d

def four(s):
    v = tuple(float(x) for x in s.split(","))
    if len(v) != 4:
        raise argparse.ArgumentTypeError("needs exactly four comma-separated numbers")
    return v

class MaterialError(Exception):
    pass

def shader_package_name(d):
    """Name of the shader package a material uses (for example 'iris.shpk'), or None."""
    try:
        ver, fsize, dsize, ssize, shoff, tc, uvc, csc, addsz = struct.unpack_from("<IHHHHBBBB", d, 0)
        if ver != 0x01030000:
            return None
        strings_at = 16 + 4 * (tc + uvc + csc)
        end = d.index(b"\0", strings_at + shoff)
        return bytes(d[strings_at + shoff:end]).decode(errors="replace")
    except (struct.error, ValueError):
        return None

def has_luminis(d):
    try:
        return name_id("g_LuminisColor") in read_constants(d)[0]
    except (struct.error, MaterialError):
        return False

def read_constants(d):
    ver, fsize, dsize, ssize, shoff, tc, uvc, csc, addsz = struct.unpack_from("<IHHHHBBBB", d, 0)
    if ver != 0x01030000 or fsize != len(d):
        raise MaterialError("not a material file this tool understands (version or size mismatch)")
    hdr = 16 + 4 * (tc + uvc + csc) + ssize + addsz + dsize
    vsz, kc, cc, sc = struct.unpack_from("<HHHH", d, hdr)
    consts_at = hdr + 12 + 8 * kc
    vals_at = consts_at + 8 * cc + 12 * sc
    if vals_at + vsz != len(d):
        raise MaterialError("material layout doesn't add up")
    consts = {struct.unpack_from("<I", d, consts_at + 8 * i)[0]: struct.unpack_from("<HH", d, consts_at + 8 * i + 4)
              for i in range(cc)}
    return consts, vals_at

def apply_luminis(data, values=None, glow_texture=None, glow_texture2=None):
    """Add missing Luminis settings (with values[key] or defaults) and update the ones given.
    Returns (new bytes, action text, {key: tuple of 4 floats})."""
    values = values or {}
    d = bytearray(data)
    consts, vals_at = read_constants(d)
    ver, fsize, dsize, ssize, shoff, tc, uvc, csc, addsz = struct.unpack_from("<IHHHHBBBB", d, 0)
    hdr = 16 + 4 * (tc + uvc + csc) + ssize + addsz + dsize
    vsz, kc, cc, sc = struct.unpack_from("<HHHH", d, hdr)
    samps_at = hdr + 12 + 8 * kc + 8 * cc
    ids = {k: name_id(n) for k, n in NAMES.items()}
    missing = [k for k in NAMES if ids[k] not in consts]
    shader_defaults = {**DEFAULTS, **SHADER_DEFAULTS.get((shader_package_name(d) or "").lower(), {})}
    if missing:
        new_entries = b"".join(struct.pack("<IHH", ids[k], vsz + 16 * j, 16) for j, k in enumerate(missing))
        new_vals = b"".join(struct.pack("<4f", *(values.get(k) or shader_defaults[k])) for k in missing)
        d = d[:samps_at] + new_entries + d[samps_at:] + new_vals
        struct.pack_into("<H", d, 4, len(d))
        struct.pack_into("<HHHH", d, hdr, vsz + len(new_vals), kc, cc + len(missing), sc)
        consts, vals_at = read_constants(d)
    for k in NAMES:
        v = values.get(k)
        if v is not None and k not in missing:
            off, size = consts[ids[k]]
            if size != 16:
                raise MaterialError(f"{NAMES[k]} has unexpected size {size}")
            struct.pack_into("<4f", d, vals_at + off, *v)
    action = ("added " + ", ".join(NAMES[k] for k in missing)) if missing else "updated"
    if glow_texture:
        d = set_glow_texture(d, glow_texture.strip().replace("\\", "/").lower())
    if glow_texture2:
        d = set_glow_texture(d, glow_texture2.strip().replace("\\", "/").lower(), "g_SamplerLuminis2")
    consts, vals_at = read_constants(d)   # verifies the layout again
    result = {k: struct.unpack_from("<4f", d, vals_at + consts[ids[k]][0]) for k in NAMES}
    return bytes(d), action, result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    for k in NAMES:
        ap.add_argument(f"--{k}", type=four)
    ap.add_argument("--glow-texture")
    ap.add_argument("--glow-texture2")
    a = ap.parse_args()
    try:
        d, action, result = apply_luminis(pathlib.Path(a.src).read_bytes(),
                                          {k: getattr(a, k) for k in NAMES if getattr(a, k) is not None},
                                          a.glow_texture, a.glow_texture2)
    except (MaterialError, struct.error) as e:
        fail(str(e))
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_bytes(d)
    print(f"Luminis settings ({action}):")
    for k in NAMES:
        print(f"  {NAMES[k]:18s} = " + ", ".join(f"{x:g}" for x in (round(y, 4) for y in result[k])))
    print(f"Wrote {a.out}")

if __name__ == "__main__":
    main()
