# clean_dev_mod.py - strip the Luminis Dev mod down to the production files.
#
# Usage (from D:\luminis):
#   python tools\clean_dev_mod.py            show what would be removed (changes nothing)
#   python tools\clean_dev_mod.py --apply    do it
#
# Keeps only the shader packages (shader/sm5/shpk/*.shpk) and dev-kit files
# (penumbra/shpk_devkit/*.json). Every other redirection, option group (such as Eye Mask) and
# file in the mod folder is MOVED to D:\luminis\archive\<date-time>\ (never deleted), along with
# a copy of the old meta.json. Afterwards, click Reload Mod for Luminis Dev in Penumbra.
import argparse, datetime, json, pathlib, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MOD = pathlib.Path(r"D:\SquareEnix\Luminis Dev")

def keep(game_path):
    gp = game_path.replace("\\", "/").lower()
    return (gp.startswith("shader/sm5/shpk/") and gp.endswith(".shpk")) or \
           (gp.startswith("penumbra/shpk_devkit/") and gp.endswith(".json"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--mod", default=str(MOD))
    a = ap.parse_args()
    mod = pathlib.Path(a.mod)
    meta_path = mod / "meta.json"
    if not meta_path.exists():
        sys.exit(f"STOPPED: {meta_path} not found")
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    if meta.get("FileVersion", 0) < 4:
        sys.exit("STOPPED: this mod uses the older Penumbra layout; open it in Penumbra once so it updates, then retry")

    files = meta.get("DefaultData", {}).get("Files", {}) or {}
    kept = {gp: rel for gp, rel in files.items() if keep(gp)}
    dropped = {gp: rel for gp, rel in files.items() if not keep(gp)}
    groups = meta.get("Groups", []) or []
    keep_files = {str(pathlib.PureWindowsPath(rel)).lower() for rel in kept.values()}

    # Every file in the mod folder that isn't a kept file (or meta.json / Penumbra's own backups)
    to_move = []
    for p in sorted(mod.rglob("*")):
        if not p.is_file():
            continue
        rel = str(pathlib.PureWindowsPath(p.relative_to(mod))).lower()
        if rel in keep_files or rel == "meta.json":
            continue
        to_move.append(p)

    print(f"Keeping {len(kept)} redirection(s):")
    for gp in sorted(kept):
        print(f"  keep    {gp}")
    for gp in sorted(dropped):
        print(f"  remove  {gp}")
    for g in groups:
        print(f"  remove  option group '{g.get('Name')}' ({len(g.get('Options', []))} options)")
    print(f"\n{len(to_move)} file(s) will be moved to the archive.")
    missing = [k for k in ("iris", "hair", "skin") if f"shader/sm5/shpk/{k}.shpk" not in kept]
    if missing:
        print(f"Note: no {', '.join(missing)}.shpk redirection in the mod; the production mod will lack those parts.")
    if not a.apply:
        print("\nNothing was changed. Run again with --apply to do it.")
        return

    archive = ROOT / "archive" / datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    archive.mkdir(parents=True, exist_ok=True)
    shutil.copy2(meta_path, archive / "meta.json.before_cleanup")
    for p in to_move:
        dest = archive / "files" / p.relative_to(mod)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(p), str(dest))
    # remove now-empty folders
    for d in sorted((d for d in mod.rglob("*") if d.is_dir()), key=lambda x: -len(x.parts)):
        if not any(d.iterdir()):
            d.rmdir()

    meta["DefaultData"]["Files"] = kept
    meta["Groups"] = []
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone. Moved {len(to_move)} file(s) to {archive}")
    print("In Penumbra, click Reload Mod for Luminis Dev now.")
    print("Your test glow (eye masks, hair and body test materials) is no longer in this mod; use glow mods for those.")

if __name__ == "__main__":
    main()
