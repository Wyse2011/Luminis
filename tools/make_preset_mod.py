# make_preset_mod.py - build a standalone Luminis mod from a material, glow settings, and optional
# extra files (for example eye masks and hue maps). Good for eye and hair glow mods and showcases.
#
# Usage (from D:\luminis):
#   python tools\make_preset_mod.py --name "NAME" --material FILE GAME_PATH [settings] [--file FILE GAME_PATH ...]
#
#   --material FILE GAME_PATH   material to give Luminis settings (repeatable)
#   --file FILE GAME_PATH       any extra file to include as-is, such as a texture (repeatable)
#   settings: the same options as mtrl_luminis.py, four comma-separated numbers each:
#     --color R,G,B,INTENSITY   --light START,END,MODE,SENS   --misc SOURCE,AREAMIX,AREA,DEBUG
#     --detail DETAIL,GAIN,RAINBOWLEN,RAINBOWSHIFT   --highlight R,G,B,ON
#   --mod-dir FOLDER   Penumbra mod folder (default D:\SquareEnix)
#   --update           allow replacing an existing mod with the same name
import argparse, json, pathlib, sys, uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mtrl_luminis as ml

def fail(msg):
    sys.exit(f"STOPPED: {msg}\nNothing was written.")

def four(s):
    v = tuple(float(x) for x in s.split(","))
    if len(v) != 4:
        raise argparse.ArgumentTypeError("needs exactly four comma-separated numbers")
    return v

def norm(p):
    p = p.strip().replace("\\", "/").lower()
    if ":" in p or p.startswith("/") or "/" not in p:
        fail(f"'{p}' doesn't look like a game path")
    return p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--material", nargs=2, action="append", metavar=("FILE", "GAME_PATH"), required=True)
    ap.add_argument("--file", nargs=2, action="append", metavar=("FILE", "GAME_PATH"), default=[])
    for k in ml.NAMES:
        ap.add_argument(f"--{k}", type=four)
    ap.add_argument("--mod-dir", default=r"D:\SquareEnix")
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    values = {k: getattr(a, k) for k in ml.NAMES if getattr(a, k) is not None}

    for src, _ in a.material + a.file:
        if not pathlib.Path(src).is_file():
            fail(f"{src} not found")
    mod = pathlib.Path(a.mod_dir) / "".join(c for c in a.name if c not in '<>:"/\\|?*').strip()
    if mod.exists() and not a.update:
        fail(f"{mod} already exists; use --update to replace it, or pick another --name")
    mod.mkdir(parents=True, exist_ok=True)

    files = {}
    def put(gp, payload):
        rel = pathlib.PureWindowsPath(*gp.split("/"))
        dest = mod / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        files[gp] = str(rel)

    for src, gp in a.material:
        new, _, result = ml.apply_luminis(pathlib.Path(src).read_bytes(), values)
        put(norm(gp), new)
        c = result["color"]
        print(f"material  {norm(gp)}  (intensity {c[3]:g})")
    for src, gp in a.file:
        put(norm(gp), pathlib.Path(src).read_bytes())
        print(f"file      {norm(gp)}")

    meta_path = mod / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig")) if meta_path.exists() else {
        "FileVersion": 4, "Identifier": str(uuid.uuid4()), "Name": a.name.strip(), "Author": "Wyse",
        "Description": "Luminis glow mod. Requires the Luminis mod; give this mod a higher priority than "
                       "Luminis and any mod it builds on. Fine-tune the glow in Penumbra's material editor "
                       "(Luminis Glow section)."}
    meta.setdefault("DefaultData", {})["Files"] = files
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nCreated {mod}")
    print("In Penumbra: Settings > Rediscover Mods, enable it, and give it a higher priority than Luminis.")

if __name__ == "__main__":
    main()
