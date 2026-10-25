# mdl_merge.py - put two models on one item: merges model B's meshes into model A.
#
# Usage (from D:\luminis):
#   python tools\mdl_merge.py A.mdl B.mdl OUT.mdl
#
# A is the item you wear (its file name and slot are kept); B's meshes, materials and bones are added.
# Works for simple single-LOD models without shape keys (most accessories, ears, horns, earrings).
# The merged model asks for B's materials too: redirect them under A's item folder in your mod
# (the script prints the exact game paths). Checks the result before writing it.
import pathlib, sys
import struct

LOD_FMT = "<HHffHHHHHHHHIIIIIIII"      # 60 bytes
MESH_FMT = "<HHIHHHHI3I3BB"            # 36 bytes
SUB_FMT = "<IIIHH"                     # 16 bytes
HDR_FMT = "<fHHHHHHHHHBBHBBffHHBBBBHHH6s"  # model header, 56 bytes

class Mdl:
    pass

def read(data):
    m = Mdl()
    (m.version, stack, runtime, vdcount, matcount) = struct.unpack_from("<IIIHH", data, 0)
    m.vtx_off = list(struct.unpack_from("<3I", data, 0x10))
    m.idx_off = list(struct.unpack_from("<3I", data, 0x1C))
    m.vtx_size = list(struct.unpack_from("<3I", data, 0x28))
    m.idx_size = list(struct.unpack_from("<3I", data, 0x34))
    m.lod_count, m.idx_stream, m.edge_geo, _ = struct.unpack_from("<BBBB", data, 0x40)
    p = 0x44
    m.vdecls = [data[p + 136 * i:p + 136 * (i + 1)] for i in range(vdcount)]
    p += 136 * vdcount
    assert stack == 136 * vdcount, "unexpected stack size"
    runtime_start = p
    scount, ssize = struct.unpack_from("<HxxI", data, p); p += 8
    m.strings = data[p:p + ssize]; p += ssize
    h = struct.unpack_from(HDR_FMT, data, p); p += 56
    m.hdr = list(h)
    (radius, meshc, attrc, subc, matc, bonec, btc, shapec, shapemc, shapevc, lodc, flags1, elemc,
     tsmc, flags2, mco, sco, cull, tssc, flags3, bgm, bgc, unk6, btarr, unk8, unk9, pad) = h
    assert attrc == 0 and shapec == 0 and elemc == 0 and tsmc == 0 and tssc == 0 and not (flags2 & 0x10), \
        "model uses features this merger doesn't handle"
    m.lods = [list(struct.unpack_from(LOD_FMT, data, p + 60 * i)) for i in range(3)]; p += 180
    m.meshes = [list(struct.unpack_from(MESH_FMT, data, p + 36 * i)) for i in range(meshc)]; p += 36 * meshc
    m.subs = [list(struct.unpack_from(SUB_FMT, data, p + 16 * i)) for i in range(subc)]; p += 16 * subc
    m.mat_offs = list(struct.unpack_from(f"<{matc}I", data, p)); p += 4 * matc
    m.bone_offs = list(struct.unpack_from(f"<{bonec}I", data, p)); p += 4 * bonec
    if m.version <= 0x1000005:
        m.bonetables = []
        for i in range(btc):
            idx = struct.unpack_from("<64H", data, p); cnt = data[p + 128]; p += 132
            m.bonetables.append(list(idx[:cnt]))
    else:
        # v6: per table (offset, count); offset counts 4-byte steps from the table's own entry to its data
        heads = [struct.unpack_from("<HH", data, p + 4 * i) for i in range(btc)]; p += 4 * btc
        arr = struct.unpack_from(f"<{btarr}H", data, p); p += 2 * btarr
        if (2 * btarr) % 4: p += 2
        starts = [2 * (i + o - btc) for i, (o, c) in enumerate(heads)]
        m.bonetables = [list(arr[st:st + c]) for st, (o, c) in zip(starts, heads)]
        m.bt_starts, m.bt_total, m.bt_raw = starts, btarr, list(arr)   # original layout (byte-exact rewrites)
    m.hdr_lod_offs = (list(struct.unpack_from("<3I", data, 0x10)), list(struct.unpack_from("<3I", data, 0x1C)))
    bm_size = struct.unpack_from("<I", data, p)[0]; p += 4
    m.bonemap = list(struct.unpack_from(f"<{bm_size // 2}H", data, p)); p += bm_size
    padn = data[p]; m.pad_bytes = data[p + 1:p + 1 + padn]; p += 1 + padn
    m.padn = padn
    m.bboxes = [struct.unpack_from("<8f", data, p + 32 * i) for i in range(4)]; p += 128
    m.bone_bboxes = [struct.unpack_from("<8f", data, p + 32 * i) for i in range(bonec)]; p += 32 * bonec
    assert p == runtime_start + runtime, f"runtime size mismatch {p - runtime_start} vs {runtime}"
    assert m.vtx_off[0] == p, "vertex data doesn't follow the header"
    m.vtx = data[m.vtx_off[0]:m.vtx_off[0] + m.vtx_size[0]]
    m.idx = data[m.idx_off[0]:m.idx_off[0] + m.idx_size[0]]
    m.tail = data[m.idx_off[0] + m.idx_size[0]:]          # leftover bytes some tools leave at the end
    assert m.lod_count == 1, "only single-LOD models"
    return m

def string_at(m, off):
    return m.strings[off:m.strings.index(b"\0", off)].decode()

def write(m, keep_padding=False):
    # strings: bones, then materials (rebuild offsets)
    bones = [string_at(m, o) for o in m.bone_offs]
    mats = [string_at(m, o) for o in m.mat_offs]
    strings = b""; bone_offs = []; mat_offs = []
    for b in bones: bone_offs.append(len(strings)); strings += b.encode() + b"\0"
    for x in mats: mat_offs.append(len(strings)); strings += x.encode() + b"\0"
    while len(strings) % 4: strings += b"\0"
    body = bytearray()
    body += struct.pack("<HxxI", len(bones) + len(mats), len(strings)) + strings
    h = list(m.hdr)
    h[1] = len(m.meshes); h[3] = len(m.subs); h[4] = len(mats); h[5] = len(bones); h[6] = len(m.bonetables)
    btc = len(m.bonetables)
    if keep_padding and hasattr(m, "bt_starts"):          # reproduce the original table layout
        arr = list(m.bt_raw); starts = m.bt_starts
        for st, t in zip(starts, m.bonetables): arr[st:st + len(t)] = t
    else:                                                 # compact: each table padded to an even count
        arr, starts = [], []
        for t in m.bonetables:
            starts.append(len(arr)); arr += t + ([0] if len(t) % 2 else [])
    heads = [(st // 2 + btc - i, len(t)) for i, (st, t) in enumerate(zip(starts, m.bonetables))]
    h[23] = len(arr)
    body += struct.pack(HDR_FMT, *h)
    lods_at = len(body)
    for l in m.lods: body += struct.pack(LOD_FMT, *l)
    for x in m.meshes: body += struct.pack(MESH_FMT, *x)
    for s in m.subs: body += struct.pack(SUB_FMT, *s)
    body += struct.pack(f"<{len(mat_offs)}I", *mat_offs)
    body += struct.pack(f"<{len(bone_offs)}I", *bone_offs)
    for o, c in heads: body += struct.pack("<HH", o, c)
    body += struct.pack(f"<{len(arr)}H", *arr)
    if (2 * len(arr)) % 4: body += b"\0\0"
    body += struct.pack("<I", 2 * len(m.bonemap)) + struct.pack(f"<{len(m.bonemap)}H", *m.bonemap)
    # padding so the vertex data starts 8-byte aligned (header 0x44 + stack + runtime)
    base = 0x44 + 136 * len(m.vdecls)
    padn = m.padn if keep_padding else (8 - (base + len(body) + 1 + 128 + 32 * len(bones)) % 8) % 8
    body += bytes([padn]) + (m.pad_bytes if keep_padding else b"\0" * padn)
    for b in m.bboxes: body += struct.pack("<8f", *b)
    for b in m.bone_bboxes: body += struct.pack("<8f", *b)
    vtx_off = base + len(body)
    idx_off = vtx_off + len(m.vtx)
    if not keep_padding:      # LOD 0 describes the actual buffers
        l0 = list(m.lods[0]); l0[16], l0[17], l0[18], l0[19] = len(m.vtx), len(m.idx), vtx_off, idx_off
        body[lods_at:lods_at + 60] = struct.pack(LOD_FMT, *l0)
    hdr = struct.pack("<IIIHH", m.version, 136 * len(m.vdecls), len(body), len(m.vdecls), len(mats))
    if keep_padding and hasattr(m, "hdr_lod_offs"):       # unused LOD slots as in the original
        (ov, oi) = m.hdr_lod_offs
        fix = lambda o, cur: [cur] + [cur + (x - o[0]) if x else 0 for x in o[1:]]
        hdr += struct.pack("<3I", *fix(ov, vtx_off)) + struct.pack("<3I", *fix(oi, idx_off))
    else:
        hdr += struct.pack("<3I", vtx_off, 0, 0) + struct.pack("<3I", idx_off, 0, 0)
    hdr += struct.pack("<3I", len(m.vtx), 0, 0) + struct.pack("<3I", len(m.idx), 0, 0)
    hdr += struct.pack("<BBBB", 1, m.idx_stream, m.edge_geo, 0)
    out = hdr + b"".join(m.vdecls) + bytes(body) + m.vtx + m.idx + (m.tail if keep_padding else b"")
    return out


def _union_box(a, b):
    return tuple(min(a[i], b[i]) for i in range(4)) + tuple(max(a[i], b[i]) for i in range(4, 8))

def _pad16(buf):
    return buf + b"\0" * ((16 - len(buf) % 16) % 16)

def merge(a, b):
    """Combine model b into model a (same skeleton; b's meshes are added after a's)."""
    import copy
    m = copy.deepcopy(a)
    a_bones = [string_at(a, o) for o in a.bone_offs]
    b_bones = [string_at(b, o) for o in b.bone_offs]
    bones = list(a_bones)
    for n in b_bones:
        if n not in bones: bones.append(n)
    bmap = [bones.index(n) for n in b_bones]
    mats = [string_at(a, o) for o in a.mat_offs] + [string_at(b, o) for o in b.mat_offs]
    # string table rebuilt by write(); stash names via a fresh table
    st = b""; m.bone_offs = []; m.mat_offs = []
    for n in bones: m.bone_offs.append(len(st)); st += n.encode() + b"\0"
    for n in mats: m.mat_offs.append(len(st)); st += n.encode() + b"\0"
    m.strings = st
    a_vtx, a_idx = _pad16(a.vtx), _pad16(a.idx)
    idx_shift = len(a_idx) // 2
    m.vdecls = a.vdecls + b.vdecls
    m.meshes = [list(x) for x in a.meshes]
    # mesh fields: 0 vertex count, 2 index count, 3 material, 4 first submesh, 5 submesh count,
    # 6 bone table, 7 start index, 8-10 vertex buffer offsets, 11-13 strides, 14 stream count
    for x in b.meshes:
        x = list(x)
        x[3] += len(a.mat_offs)
        x[4] += len(a.subs)
        x[6] += len(a.bonetables)
        x[7] += idx_shift
        for k in range(x[14] & 3): x[8 + k] += len(a_vtx)      # low 2 bits = stream count
        m.meshes.append(x)
    m.subs = [list(x) for x in a.subs]
    for x in b.subs:
        x = list(x); x[0] += idx_shift; x[3] += len(a.bonemap); m.subs.append(x)
    m.bonetables = [list(t) for t in a.bonetables] + [[bmap[i] for i in t] for t in b.bonetables]
    m.bonemap = list(a.bonemap) + [bmap[i] if i < len(bmap) else i for i in b.bonemap]
    m.vtx = a_vtx + b.vtx
    m.idx = a_idx + b.idx
    total = len(m.meshes)
    l0 = list(a.lods[0])
    l0[0], l0[1] = 0, total
    for k in (4, 6, 10):                   # water, shadow, vertical fog: empty ranges after the meshes
        l0[k] = total
    l0[12] = 0; l0[14] = (a.lods[0][14] or 0) + (b.lods[0][14] or 0)   # edge geometry size, polygon count
    m.lods = [l0] + [list(x) for x in a.lods[1:]]
    m.bboxes = [_union_box(x, y) for x, y in zip(a.bboxes, b.bboxes)]
    bb = {n: box for n, box in zip(a_bones, a.bone_bboxes)}
    for n, box in zip(b_bones, b.bone_bboxes):
        bb[n] = _union_box(bb[n], box) if n in bb else box
    m.bone_bboxes = [bb[n] for n in bones]
    m.hdr = list(a.hdr); m.hdr[0] = max(a.hdr[0], b.hdr[0])     # radius
    m.tail = b""
    return m

def validate(data):
    """Re-read a model and check every mesh's buffers and indices stay in range."""
    m = read(data)
    problems = []
    nv = len(m.vtx); ni = len(m.idx) // 2
    idx = struct.unpack(f"<{ni}H", m.idx)
    for k, x in enumerate(m.meshes):
        vcount, icount, mat, sub0, subn, bt, start = x[0], x[2], x[3], x[4], x[5], x[6], x[7]
        offs, strides, streams = x[8:11], x[11:14], x[14] & 3     # low 2 bits = stream count
        for s_ in range(streams):
            if offs[s_] + strides[s_] * vcount > nv: problems.append(f"mesh {k}: stream {s_} past vertex data")
        if start + icount > ni: problems.append(f"mesh {k}: indices past index data")
        elif icount and max(idx[start:start + icount]) >= vcount: problems.append(f"mesh {k}: index beyond its vertices")
        if mat >= len(m.mat_offs): problems.append(f"mesh {k}: bad material")
        if bt >= len(m.bonetables): problems.append(f"mesh {k}: bad bone table")
        if sub0 + subn > len(m.subs): problems.append(f"mesh {k}: bad submeshes")
        for sidx in range(sub0, min(sub0 + subn, len(m.subs))):
            so, sc = m.subs[sidx][0], m.subs[sidx][1]
            if so < start or so + sc > start + icount: problems.append(f"mesh {k}: submesh {sidx} outside mesh")
    for t in m.bonetables:
        if any(i >= len(m.bone_offs) for i in t): problems.append("bone table references a missing bone")
    return m, problems


def main():
    if len(sys.argv) != 4:
        sys.exit("usage: python tools\\mdl_merge.py A.mdl B.mdl OUT.mdl")
    a_path, b_path, out_path = (pathlib.Path(x) for x in sys.argv[1:])
    try:
        a, b = read(a_path.read_bytes()), read(b_path.read_bytes())
    except AssertionError as e:
        sys.exit(f"STOPPED: {e} (this model needs Blender instead)")
    a_bones = {string_at(a, o) for o in a.bone_offs}
    new_bones = [string_at(b, o) for o in b.bone_offs if string_at(b, o) not in a_bones]
    data = write(merge(a, b))
    m, problems = validate(data)
    if problems:
        sys.exit("STOPPED: the merged model failed its checks:\n  " + "\n  ".join(problems[:10]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    print(f"Wrote {out_path} ({len(a.meshes)} + {len(b.meshes)} meshes, {len(data) / 1e6:.1f} MB); checks passed")
    if new_bones:
        print(f"Note: B adds bones A didn't have: {', '.join(new_bones)}")
    mats_b = [string_at(b, o) for o in b.mat_offs]
    print("Materials B needs (redirect these under A's item folder, next to A's own materials):")
    for x in mats_b:
        print(f"  {x.lstrip('/')}")


if __name__ == "__main__":
    main()
