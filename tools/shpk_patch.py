# shpk_patch.py - replace pixel/vertex shader blobs inside a .shpk without Penumbra's editor.
#
# Usage (from D:\luminis):
#   python tools\shpk_patch.py IN.shpk OUT.shpk ORIG_DIR NEW_DIR INDEX [INDEX ...]
#
#   IN.shpk   the shader package to start from (never modified)
#   OUT.shpk  where to write the patched package
#   ORIG_DIR  folder with the original exported blobs, named ps_<N>.dxbc
#   NEW_DIR   folder with the replacements, named ps_<N>_<anything>.dxbc (or ps_<N>.dxbc)
#   INDEX     pixel shader numbers to replace, e.g. 3 12 19   (or "all" = every original in ORIG_DIR)
#
# How it works: it finds each original blob's bytes inside the package, then finds the
# single table entry (offset, size) that points at it. New blobs are appended to the end of
# the blob section and their entries repointed. If anything doesn't match exactly, it stops
# without writing. Penumbra's file format: magic 'ShPk', version, DX magic, file length,
# blob section offset, string section offset, ...
import pathlib, struct, sys

def fail(msg):
    sys.exit(f"STOPPED: {msg}\nNothing was written.")

def find_new(new_dir, n):
    exact = new_dir / f"ps_{n}.dxbc"
    matches = sorted(new_dir.glob(f"ps_{n}_*.dxbc")) + ([exact] if exact.exists() else [])
    if len(matches) != 1:
        fail(f"expected exactly one replacement for ps_{n} in {new_dir}, found {[m.name for m in matches]}")
    return matches[0]

def main():
    if len(sys.argv) < 6:
        sys.exit(__doc__ if __doc__ else "see header comment for usage")
    src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    orig_dir, new_dir = pathlib.Path(sys.argv[3]), pathlib.Path(sys.argv[4])
    if sys.argv[5].lower() == "all":
        indices = sorted(int(p.stem.split("_")[1]) for p in orig_dir.glob("ps_*.dxbc")
                         if p.stem.split("_")[1].isdigit())
    else:
        indices = [int(a.lstrip("#")) for a in sys.argv[5:]]

    data = bytearray(src.read_bytes())
    if data[:4] != b"ShPk":
        fail(f"{src} does not start with 'ShPk'")
    file_len, blobs_off, strings_off = struct.unpack_from("<III", data, 12)
    if file_len != len(data) or not (0 < blobs_off <= strings_off <= len(data)):
        fail("header layout is not what this tool expects (file length / section offsets don't add up)")

    table = bytes(data[:blobs_off])
    blob_region = bytes(data[blobs_off:strings_off])
    plan = []
    for n in indices:
        orig = (orig_dir / f"ps_{n}.dxbc").read_bytes()
        new_path = find_new(new_dir, n)
        new = new_path.read_bytes()
        if new[:4] != b"DXBC" or orig[:4] != b"DXBC":
            fail(f"ps_{n}: one of the blobs is not a DXBC shader")
        pos = blob_region.find(orig)
        if pos < 0:
            fail(f"ps_{n}: original blob not found in {src.name} (wrong file, or already patched?)")
        entry = struct.pack("<II", pos, len(orig))
        hits, start = [], 0
        while (i := table.find(entry, start)) >= 0:
            hits.append(i); start = i + 1
        if len(hits) != 1:
            fail(f"ps_{n}: expected one table entry pointing at its blob, found {len(hits)}")
        plan.append((n, hits[0], new, new_path.name))

    # Append new blobs at the end of the blob section (4-byte aligned), shift the strings.
    appended = bytearray()
    base_rel = strings_off - blobs_off
    for idx, (n, entry_pos, new, _) in enumerate(plan):
        rel = base_rel + len(appended)
        struct.pack_into("<II", data, entry_pos, rel, len(new))
        appended += new + b"\0" * (-len(new) % 4)
    out_data = data[:strings_off] + appended + data[strings_off:]
    new_strings_off = strings_off + len(appended)
    struct.pack_into("<III", out_data, 12, len(out_data), blobs_off, new_strings_off)

    # Verify before writing: every entry must point at exactly its new blob,
    # and the string section must be byte-identical to the original.
    for n, entry_pos, new, _ in plan:
        rel, size = struct.unpack_from("<II", out_data, entry_pos)
        if bytes(out_data[blobs_off + rel: blobs_off + rel + size]) != new:
            fail(f"ps_{n}: verification failed")
    if bytes(out_data[new_strings_off:]) != bytes(data[strings_off:]):
        fail("string section verification failed")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(out_data)
    for n, _, new, name in plan:
        print(f"ok    ps_{n} <- {name} ({len(new)} bytes)")
    print(f"\nWrote {out} ({len(out_data)} bytes, {len(plan)} shader(s) replaced)")

if __name__ == "__main__":
    main()
