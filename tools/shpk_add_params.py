# shpk_add_params.py - add the Luminis material constants to a .shpk.
#
# Usage (from D:\luminis):
#   python tools\shpk_add_params.py IN.shpk OUT.shpk
#
# Adds nineteen float4 material parameters at the end of the material buffer:
#   g_LuminisColor  (tint RGB, intensity)            default 1, 1, 1, 0   <- intensity 0: no glow
#   g_LuminisLight  (dark start, dark end, mode, sensitivity)  default 0.02, 0.15, 1, 1
#   g_LuminisMisc   (color source, area mix, glow area, debug view)     default 1, 0.5, 0, 0
#   g_LuminisDetail (detail, detail gain, rainbow length, rainbow shift) default 0, 2, 0, 0
#   g_LuminisHighlight (highlight tint RGB, use highlight tint 0/1)      default 1, 1, 1, 0
#   g_LuminisAnim   (animation mode, speed, steps, softness)            default 0, 1, 4, 1
#   g_LuminisAnimColor (color 2 / strobe color RGB, unused)             default 0, 0, 1, 0
#   g_LuminisAnimColor3, g_LuminisAnimColor4 (colors 3 and 4 RGB, pulse min / max) default green 0.15, yellow 1
#   g_LuminisL2Color (layer 2 tint RGB, intensity)                       default 1, 1, 1, 0
#   g_LuminisL2Light (layer 2 dark start, dark end, mode, sensitivity)   default 0.02, 0.15, 0 (always), 1
#   g_LuminisL2Anim  (layer 2 animation mode, speed, steps, softness)    default 0, 1, 4, 1
#   g_LuminisL2AnimColor (layer 2 color 2 RGB, layer 2 color source)     default blue, source 2
#   g_LuminisL2AnimColor3, ...4 (layer 2's own colors 3, 4 RGB)          default green, yellow
#   g_LuminisRows1..4 (gear: per color table row 0 animated, 1 static, 2 off; rows 1-4 .. 13-16) default 0
# and grows every g_MaterialParameter buffer declaration to match. Shader blobs are untouched;
# run shpk_patch.py on the result to swap in the Luminis shaders.
#
# Layout (DX11 .shpk, version 0x0E01): 88-byte header; shader entries (20-byte header +
# 16-byte resources each); material parameter table (8 bytes each); material defaults;
# global constants/samplers/textures/...; blob section; string section. The tool checks each
# part against the others and stops without writing if anything doesn't add up.
import pathlib, struct, sys, zlib

PARAMS = [
    ("g_LuminisColor", (1.0, 1.0, 1.0, 0.0)),
    ("g_LuminisLight", (0.02, 0.15, 1.0, 1.0)),
    ("g_LuminisMisc",  (1.0, 0.5, 0.0, 0.0)),
    ("g_LuminisDetail", (0.0, 2.0, 0.0, 0.0)),
    ("g_LuminisHighlight", (1.0, 1.0, 1.0, 0.0)),
    ("g_LuminisAnim", (0.0, 1.0, 4.0, 1.0)),
    ("g_LuminisAnimColor", (0.0, 0.0, 1.0, 0.0)),
    ("g_LuminisAnimColor3", (0.0, 1.0, 0.0, 0.15)),
    ("g_LuminisAnimColor4", (1.0, 1.0, 0.0, 1.0)),
    ("g_LuminisL2Color", (1.0, 1.0, 1.0, 0.0)),
    ("g_LuminisL2Light", (0.02, 0.15, 0.0, 1.0)),
    ("g_LuminisL2Anim", (0.0, 1.0, 4.0, 1.0)),
    ("g_LuminisL2AnimColor", (0.0, 0.0, 1.0, 2.0)),
    ("g_LuminisL2AnimColor3", (0.0, 1.0, 0.0, 0.15)),
    ("g_LuminisL2AnimColor4", (1.0, 1.0, 0.0, 1.0)),
    ("g_LuminisRows1", (0.0, 0.0, 0.0, 0.0)),
    ("g_LuminisRows2", (0.0, 0.0, 0.0, 0.0)),
    ("g_LuminisRows3", (0.0, 0.0, 0.0, 0.0)),
    ("g_LuminisRows4", (0.0, 0.0, 0.0, 0.0)),
]
MATERIAL_BUFFER_ID = 0x64D12851  # g_MaterialParameter

def name_id(name):
    return zlib.crc32(name.encode(), 0xFFFFFFFF) ^ 0xFFFFFFFF

def fail(msg):
    sys.exit(f"STOPPED: {msg}\nNothing was written.")

def find_shader_entries(d, blobs_off, strings_off):
    table = d[:blobs_off]
    entries, pos = [], blobs_off
    while pos < strings_off:
        nxt = d.find(b"DXBC", pos, strings_off)
        if nxt < 0:
            break
        size = struct.unpack_from("<I", d, nxt + 24)[0]
        rel, found = nxt - blobs_off, False
        for pre in range(33):
            i = table.find(struct.pack("<II", rel - pre, size + pre))
            if i >= 0:
                entries.append(i); found = True; break
        pos = nxt + (size if found else 4)
    return sorted(entries)

def main():
    src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    d = bytearray(src.read_bytes())
    if d[:4] != b"ShPk" or d[8:12] != b"DX11":
        fail("not a DX11 .shpk")
    version = struct.unpack_from("<I", d, 4)[0]
    file_len, blobs_off, strings_off, vs_count, ps_count, mat_size = struct.unpack_from("<6I", d, 12)
    param_count, has_defaults = struct.unpack_from("<HH", d, 36)
    if file_len != len(d):
        fail("file length field doesn't match")
    if version != 0x0E01:
        print(f"warning: shpk version {version:#x}, tool was built for 0x0e01; checks below still apply")
    if has_defaults != 1:
        fail("this package has no material default values block; layout differs from expected")
    if mat_size % 16:
        fail(f"material buffer size {mat_size} is not a whole number of float4s")

    # Material parameter table starts right after the last shader entry and its resources.
    entries = find_shader_entries(d, blobs_off, strings_off)
    if len(entries) != vs_count + ps_count:
        fail(f"found {len(entries)} shader entries, header says {vs_count + ps_count}")
    last = entries[-1]
    c, s, u, t = struct.unpack_from("<HHHH", d, last + 8)
    params_start = last + 20 + 16 * (c + s + u + t)
    params_end = params_start + 8 * param_count
    defaults_end = params_end + mat_size

    existing = set()
    for k in range(param_count):
        pid, off, size = struct.unpack_from("<IHH", d, params_start + 8 * k)
        if off + size > mat_size or size == 0 or size % 4 or off % 4:
            fail(f"material parameter #{k} looks wrong (offset {off}, size {size}); layout differs from expected")
        existing.add(pid)
    new_ids = [name_id(n) for n, _ in PARAMS]
    if any(i in existing for i in new_ids):
        fail("Luminis parameters are already present in this file")

    # The global constants table follows the defaults; it must declare g_MaterialParameter at mat_size.
    old_regs, new_regs = mat_size // 16, mat_size // 16 + len(PARAMS)
    const_count = struct.unpack_from("<I", d, 40)[0]
    glob = [struct.unpack_from("<IIHHHH", d, defaults_end + 16 * k) for k in range(const_count)]
    mats = [g for g in glob if g[0] == MATERIAL_BUFFER_ID]
    if len(mats) != 1 or mats[0][5] != old_regs:
        fail("global constant table doesn't declare g_MaterialParameter where expected")

    new_params = b"".join(struct.pack("<IHH", i, mat_size + 16 * j, 16) for j, i in enumerate(new_ids))
    new_defaults = b"".join(struct.pack("<4f", *v) for _, v in PARAMS)
    grow = len(new_params) + len(new_defaults)
    o = (d[:params_end] + new_params + d[params_end:defaults_end] + new_defaults + d[defaults_end:])

    struct.pack_into("<3I", o, 12, len(o), blobs_off + grow, strings_off + grow)
    struct.pack_into("<I", o, 32, mat_size + 16 * len(PARAMS))
    struct.pack_into("<H", o, 36, param_count + len(PARAMS))

    # Grow every g_MaterialParameter declaration (per shader and global) from old_regs to new_regs.
    key, pos, grown = struct.pack("<I", MATERIAL_BUFFER_ID), 0, 0
    while (pos := o.find(key, pos, blobs_off + grow)) >= 0:
        _, stroff, strsize, istex, slot, size = struct.unpack_from("<IIHHHH", o, pos)
        if strsize == len("g_MaterialParameter") and istex == 0 and size == old_regs:
            struct.pack_into("<H", o, pos + 14, new_regs); grown += 1
        pos += 1

    # Verify: blob and string sections are byte-identical, params/defaults read back correctly.
    if bytes(o[blobs_off + grow:]) != bytes(d[blobs_off:]):
        fail("blob/string section verification failed")
    for j, (name, vals) in enumerate(PARAMS):
        pid, off, size = struct.unpack_from("<IHH", o, params_end + 8 * j)
        got = struct.unpack_from("<4f", o, params_end + len(new_params) + mat_size + 16 * j)
        if pid != new_ids[j] or off != mat_size + 16 * j or any(abs(a - b) > 1e-6 for a, b in zip(got, vals)):
            fail(f"{name}: verification failed")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(o)
    for j, (name, vals) in enumerate(PARAMS):
        print(f"added {name:16s} id {new_ids[j]:#010x}  slot [{old_regs + j}]  default {vals}")
    print(f"grew {grown} g_MaterialParameter declarations from {old_regs} to {new_regs} registers")
    print(f"Wrote {out} ({len(o)} bytes)")

if __name__ == "__main__":
    main()
