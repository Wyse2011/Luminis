# shpk_extract.py - export every shader blob from a .shpk, named by its index.
#
# Usage (from D:\luminis):
#   python tools\shpk_extract.py vanilla\2026.09.15\iris.shpk blobs\iris\all
#
# Writes vs_<N>.dxbc and ps_<N>.dxbc, numbered the same way Penumbra numbers them.
# How it works: it walks the DXBC blobs in the blob section, finds the single table entry
# (offset, size) pointing at each, and orders entries by their position in the table
# (vertex shaders first, then pixel shaders). It cross-checks the totals against the
# shader counts in the header and stops without writing if anything disagrees.
import pathlib, struct, sys

def fail(msg):
    sys.exit(f"STOPPED: {msg}\nNothing was written.")

def scan_entries(data, table, blobs_off, strings_off):
    """Fallback: find each DXBC blob and the table entry that points at it."""
    entries, pos = [], blobs_off
    while pos < strings_off:
        nxt = data.find(b"DXBC", pos, strings_off)
        if nxt < 0:
            break
        size = struct.unpack_from("<I", data, nxt + 24)[0]  # DXBC total size field
        rel, found = nxt - blobs_off, False
        for pre in range(0, 33):
            if rel - pre < 0:
                break
            key = struct.pack("<II", rel - pre, size + pre)
            start = 0
            while (i := table.find(key, start)) >= 0:
                entries.append((i, rel - pre, size + pre, pre))
                start = i + 1
                found = True
            if found:
                break
        pos = nxt + (size if found else 4)  # not found: orphaned blob from an earlier patch
    return entries

def main():
    src, out_dir = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    data = src.read_bytes()
    if data[:4] != b"ShPk":
        fail("not a .shpk file")
    file_len, blobs_off, strings_off, vs_count, ps_count = struct.unpack_from("<IIIII", data, 12)
    if file_len != len(data) or not (0 < blobs_off <= strings_off <= len(data)):
        fail("header layout is not what this tool expects")
    table = data[:blobs_off]

    # Read the shader table entry by entry (20-byte header + 16 bytes per resource, back to back
    # after the 88-byte file header). Every entry must point at DXBC data; vertex shader entries may
    # have a small header in front of it.
    entries = []  # (table position, rel offset, size, header bytes before DXBC)
    try:
        pos = 88
        for _ in range(vs_count + ps_count):
            off, size, c, s_, u, t = struct.unpack_from("<IIHHHH", data, pos)
            pre = data.find(b"DXBC", blobs_off + off, blobs_off + off + min(size, 40)) - (blobs_off + off)
            if pre < 0:
                raise ValueError
            entries.append((pos, off, size, pre))
            pos += 20 + 16 * (c + s_ + u + t)
    except (ValueError, struct.error):
        entries = scan_entries(data, table, blobs_off, strings_off)

    entries.sort()
    if len(entries) != vs_count + ps_count:
        fail(f"found {len(entries)} shader entries, header says {vs_count} vertex + {ps_count} pixel")
    # Vertex shaders come first in the table, then pixel shaders. Pixel shader entries must
    # point straight at their DXBC data (no header); check that the split is consistent.
    if any(pre != 0 for (_, _, _, pre) in entries[vs_count:]):
        fail("pixel shader entries don't look as expected (unexpected header in front of a pixel shader)")

    out_dir.mkdir(parents=True, exist_ok=True)
    for i, (_, rel, size, pre) in enumerate(entries):
        # Write only the DXBC data (skip any header), matching Penumbra's exported blobs.
        blob = data[blobs_off + rel + pre: blobs_off + rel + size]
        name = f"vs_{i}.dxbc" if i < vs_count else f"ps_{i - vs_count}.dxbc"
        (out_dir / name).write_bytes(blob)
    print(f"Wrote {vs_count} vertex and {ps_count} pixel shaders to {out_dir}")

if __name__ == "__main__":
    main()
