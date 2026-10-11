# luminis_convert_mod.py - make a Luminis copy of any Penumbra mod.
#
# Usage (from D:\luminis):
#   python tools\luminis_convert_mod.py SOURCE [options]
#
#   SOURCE   a mod folder (for example "D:\SquareEnix\Glacial Glow Ice Eyes") or a .pmp file
#
# Copies the whole mod to a new folder "<name> (Luminis)" next to your other mods, and adds the
# Luminis settings to every material that uses a Luminis shader (eyes: iris.shpk, hair: hair.shpk,
# skin: skin.shpk).
# The original mod is never changed. Afterwards, in Penumbra: Settings > Rediscover Mods (or
# restart the game), then enable the Luminis copy instead of the original.
#
# Options:
#   --out-dir FOLDER   where to create the copy (default: D:\SquareEnix, your Penumbra mod folder)
#   --name NAME        name for the copy (default: original name + " (Luminis)")
#   --shaders LIST     which shaders to convert, comma separated (default: iris.shpk,hair.shpk,skin.shpk)
#   --update           also overwrite settings in materials that already have Luminis settings
#   --color/--light/--misc/--detail/--highlight R,G,B,A   settings to use (same as mtrl_luminis.py);
#                      anything not given uses the Luminis defaults
import argparse, json, pathlib, shutil, sys, tempfile, uuid, zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mtrl_luminis as ml

DEFAULT_OUT = r"D:\SquareEnix"

def four(s):
    v = tuple(float(x) for x in s.split(","))
    if len(v) != 4:
        raise argparse.ArgumentTypeError("needs exactly four comma-separated numbers")
    return v

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    ap.add_argument("--name")
    ap.add_argument("--shaders", default="iris.shpk,hair.shpk,skin.shpk")
    ap.add_argument("--update", action="store_true")
    for k in ml.NAMES:
        ap.add_argument(f"--{k}", type=four)
    a = ap.parse_args()
    values = {k: getattr(a, k) for k in ml.NAMES if getattr(a, k) is not None}
    targets = {x.strip().lower() for x in a.shaders.split(",") if x.strip()}

    src = pathlib.Path(a.source)
    tmp = None
    if src.is_file() and src.suffix.lower() in (".pmp", ".zip"):
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="luminis_"))
        with zipfile.ZipFile(src) as z:
            z.extractall(tmp)
        mod_root = tmp
    elif src.is_dir():
        mod_root = src
    else:
        sys.exit(f"STOPPED: {src} is neither a mod folder nor a .pmp file")

    meta_path = mod_root / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig")) if meta_path.exists() else {}
    base_name = meta.get("Name") or src.stem
    new_name = a.name or f"{base_name} (Luminis)"
    folder_name = "".join(c for c in new_name if c not in '<>:"/\\|?*').strip()
    out = pathlib.Path(a.out_dir) / folder_name
    if out.exists():
        sys.exit(f"STOPPED: {out} already exists; delete it or pick another --name")

    shutil.copytree(mod_root, out)
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)

    counts, skipped, errors = {}, 0, []
    for mtrl in sorted(out.rglob("*.mtrl")):
        data = mtrl.read_bytes()
        shader = (ml.shader_package_name(data) or "").lower()
        if shader not in targets:
            continue
        if ml.has_luminis(data) and not a.update:
            skipped += 1
            continue
        try:
            new, _, _ = ml.apply_luminis(data, values)
        except Exception as e:
            errors.append(f"{mtrl.relative_to(out)}: {e}")
            continue
        mtrl.write_bytes(new)
        counts[shader] = counts.get(shader, 0) + 1

    meta["Name"] = new_name
    if "Identifier" in meta or meta.get("FileVersion", 0) >= 4:
        meta["Identifier"] = str(uuid.uuid4())
    note = "Converted for Luminis glow (luminis_convert_mod.py)."
    meta["Description"] = (meta.get("Description", "") + "\n\n" + note).strip()
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    total = sum(counts.values())
    print(f"Created {out}")
    for shader, n in sorted(counts.items()):
        print(f"  {n} {shader} material(s) given Luminis settings")
    if skipped:
        print(f"  {skipped} material(s) already had Luminis settings (use --update to overwrite)")
    for e in errors:
        print(f"  could not convert {e}")
    if total == 0 and not skipped:
        print("  No eye, hair or skin materials found in this mod; the copy is identical to the original.")
    print("\nIn Penumbra: Settings > Rediscover Mods (or restart), then enable the Luminis copy instead of the original.")

if __name__ == "__main__":
    main()
