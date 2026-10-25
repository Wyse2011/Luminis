# shpk_add_texture.py - give one pixel shader in a .shpk access to an extra material texture.
#
# Usage (from D:\luminis):
#   python tools\shpk_add_texture.py IN.shpk OUT.shpk --ps 3 --texture g_SamplerDiffuse --slot 10 --sampler g_SamplerNormal
#
# Adds a texture binding (register t<slot>, sampled with the named sampler state) to pixel
# shader --ps. The texture's name entry is copied from another shader that already uses it.
# Shader blobs are untouched. Stops without writing if anything doesn't match expectations.
import argparse, json, pathlib, struct, sys

def fail(msg):
    sys.exit(f"STOPPED: {msg}\nNothing was written.")

HEADER_SIZE = 88

def find_shader_entries(d, blobs_off, strings_off):
    """Shader entries follow the 88-byte header back to back (20-byte header + 16 bytes per
    resource). Read them directly, checking every entry points at a DXBC blob; fall back to
    a slow search if the layout doesn't check out."""
    vs_count, ps_count = struct.unpack_from("<II", d, 24)
    entries, pos = [], HEADER_SIZE
    try:
        for _ in range(vs_count + ps_count):
            off, size, c, s_, u, t = struct.unpack_from("<IIHHHH", d, pos)
            blob = d[blobs_off + off: blobs_off + off + size]
            if size < 32 or b"DXBC" not in blob[:36]:
                raise ValueError
            entries.append(pos)
            pos += 20 + 16 * (c + s_ + u + t)
        return entries
    except (ValueError, struct.error):
        return find_shader_entries_slow(d, blobs_off, strings_off)

def find_shader_entries_slow(d, blobs_off, strings_off):
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

def global_lists(d):
    """Positions of the package-wide constant, sampler and texture lists (after the material
    parameter table and its default values)."""
    file_len, blobs_off, strings_off, vs_count, ps_count, mat_size = struct.unpack_from("<6I", d, 12)
    param_count = struct.unpack_from("<H", d, 36)[0]
    const_count = struct.unpack_from("<I", d, 40)[0]
    samp_count, tex_count = struct.unpack_from("<HH", d, 44)
    entries = find_shader_entries(d, blobs_off, strings_off)
    last = entries[-1]
    c, s_, u, t = struct.unpack_from("<HHHH", d, last + 8)
    defaults_end = last + 20 + 16 * (c + s_ + u + t) + 8 * param_count + mat_size
    return {"consts": defaults_end, "samplers": defaults_end + 16 * const_count,
            "textures": defaults_end + 16 * (const_count + samp_count), "tex_count": tex_count,
            "end": defaults_end + 16 * (const_count + samp_count + tex_count)}

def read_res(d, pos, strings_off):
    rid, so, ss, istex, slot, size = struct.unpack_from("<IIHHHH", d, pos)
    return dict(id=rid, stroff=so, strsize=ss, istex=istex, slot=slot, size=size,
                name=bytes(d[strings_off + so: strings_off + so + ss]).decode(errors="replace"))

def add_global_texture(d, name):
    """Declare a new material-provided texture (like g_SamplerDiffuse) in the package-wide list,
    adding its name to the string table. Returns the new package bytes."""
    import zlib
    file_len, blobs_off, strings_off = struct.unpack_from("<III", d, 12)
    g = global_lists(d)
    texs = [read_res(d, g["textures"] + 16 * k, strings_off) for k in range(g["tex_count"])]
    if any(t_["name"] == name for t_ in texs):
        print(f"{name} is already declared")
        return d
    # Model the new entry on an existing material-provided texture (slot 2), preferably the color texture.
    diffuse = [t_ for t_ in texs if t_["name"] == "g_SamplerDiffuse"] or \
              [t_ for t_ in texs if t_["istex"] == 1 and t_["slot"] == 2]
    if not diffuse:
        fail("package has no material texture to model the new one on")
    rid = zlib.crc32(name.encode(), 0xFFFFFFFF) ^ 0xFFFFFFFF
    stroff = len(d) - strings_off           # new name goes at the very end of the string table
    entry = struct.pack("<IIHHHH", rid, stroff, len(name), diffuse[0]["istex"], diffuse[0]["slot"], diffuse[0]["size"])
    o = d[:g["end"]] + entry + d[g["end"]:] + name.encode() + b"\0"
    struct.pack_into("<III", o, 12, len(o), blobs_off + 16, strings_off + 16)
    struct.pack_into("<H", o, 46, g["tex_count"] + 1)
    if bytes(o[blobs_off + 16: blobs_off + 16 + (strings_off - blobs_off)]) != bytes(d[blobs_off:strings_off]):
        fail("blob verification failed")
    new = read_res(o, global_lists(o)["textures"] + 16 * g["tex_count"], strings_off + 16)
    if new["name"] != name or new["id"] != rid:
        fail("global texture verification failed")
    print(f"declared new material texture {name} (id {rid:#010x})")
    return o

def resources(d, entry, strings_off):
    c, s, u, t = struct.unpack_from("<HHHH", d, entry + 8)
    out = []
    for k in range(c + s + u + t):
        rid, so, ss, istex, slot, size = struct.unpack_from("<IIHHHH", d, entry + 20 + 16 * k)
        name = bytes(d[strings_off + so: strings_off + so + ss]).decode(errors="replace")
        out.append(dict(id=rid, stroff=so, strsize=ss, istex=istex, slot=slot, size=size, name=name))
    return (c, s, u, t), out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--ps", type=int)
    ap.add_argument("--texture")
    ap.add_argument("--slot", type=int)
    ap.add_argument("--sampler")
    ap.add_argument("--bindings", help="JSON list from luminis_asm.py; adds every entry with add_binding")
    ap.add_argument("--declare", help="first declare new material textures, comma separated (e.g. g_SamplerLuminis,g_SamplerLuminis2)")
    a = ap.parse_args()
    if a.bindings:
        jobs = [b for b in json.loads(pathlib.Path(a.bindings).read_text()) if b.get("add_binding")]
        jobs = [(b["ps"], b["texture"], b["slot"], b["sampler"]) for b in jobs]
    elif None not in (a.ps, a.texture, a.slot, a.sampler):
        jobs = [(a.ps, a.texture, a.slot, a.sampler)]
    elif a.declare:
        jobs = []
    else:
        fail("give --ps/--texture/--slot/--sampler, or --bindings FILE")
    d = bytearray(pathlib.Path(a.src).read_bytes())
    if a.declare:
        for name in [x.strip() for x in a.declare.split(",") if x.strip()]:
            d = bytearray(add_global_texture(d, name))
    for job in jobs:
        d = add_one(d, *job)
    pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.out).write_bytes(d)
    print(f"Wrote {a.out} ({len(d)} bytes, {len(jobs)} binding(s) added)")

def add_one(d, ps, texture, slot, sampler_name):
    if d[:4] != b"ShPk" or d[8:12] != b"DX11":
        fail("not a DX11 .shpk")
    file_len, blobs_off, strings_off, vs_count, ps_count = struct.unpack_from("<5I", d, 12)
    if file_len != len(d):
        fail("file length field doesn't match")
    entries = find_shader_entries(d, blobs_off, strings_off)
    if len(entries) != vs_count + ps_count:
        fail(f"found {len(entries)} shader entries, header says {vs_count + ps_count}")
    if not 0 <= ps < ps_count:
        fail(f"pixel shader #{ps} doesn't exist")

    target = entries[vs_count + ps]
    (c, s, u, t), res = resources(d, target, strings_off)
    if any(r["istex"] == 1 and r["name"] == texture for r in res):
        fail(f"pixel shader #{ps} already uses {texture}")
    if any(r["istex"] == 1 and r["slot"] == slot for r in res[c + s + u:]):
        fail(f"register t{slot} is already used by pixel shader #{ps}")
    samplers = [r for r in res[c:c + s] if r["name"] == sampler_name]
    if len(samplers) != 1:
        fail(f"pixel shader #{ps} has no sampler named {sampler_name}")

    # Copy the texture's identity (id + name string) from any shader that already uses it.
    donor = None
    for e in entries:
        _, rs = resources(d, e, strings_off)
        for r in rs:
            if r["istex"] == 1 and r["name"] == texture:
                donor = r; break
        if donor:
            break
    if not donor:
        g = global_lists(d)
        for k in range(g["tex_count"]):
            r = read_res(d, g["textures"] + 16 * k, strings_off)
            if r["istex"] == 1 and r["name"] == texture:
                donor = r; break
    if not donor:
        fail(f"this package doesn't know a texture named {texture}")

    new_res = struct.pack("<IIHHHH", donor["id"], donor["stroff"], donor["strsize"], 1, slot, samplers[0]["slot"])
    insert_at = target + 20 + 16 * (c + s + u + t)
    o = d[:insert_at] + new_res + d[insert_at:]
    struct.pack_into("<HHHH", o, target + 8, c, s, u, t + 1)
    struct.pack_into("<3I", o, 12, len(o), blobs_off + 16, strings_off + 16)

    # Verify: blobs/strings unchanged, and the shader's resource list reads back as expected.
    if bytes(o[blobs_off + 16:]) != bytes(d[blobs_off:]):
        fail("blob/string verification failed")
    (_, _, _, t2), res2 = resources(o, target, strings_off + 16)
    last = res2[-1]
    if t2 != t + 1 or last["name"] != texture or last["slot"] != slot or res2[:-1] != res:
        fail("resource list verification failed")

    print(f"pixel shader #{ps}: added texture {texture} at t{slot}, sampled with {sampler_name} (s{samplers[0]['slot']})")
    return o

if __name__ == "__main__":
    main()
