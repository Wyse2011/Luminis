# luminis_vanilla.py - give every vanilla eye and hair material Luminis settings, in one mod.
#
# Usage (from D:\luminis):
#   python tools\luminis_vanilla.py [options]
#
# Reads the game's own archives (read-only), finds every eye (iris) and hair material for every
# race, face and hairstyle, adds the Luminis settings, and writes them into a Penumbra mod
# (default "Luminis Vanilla Materials" in D:\SquareEnix). Afterwards, in Penumbra:
# Settings > Rediscover Mods, enable the new mod, and give it a LOWER priority than Luminis Dev
# and any converted mods, so those win where they overlap.
#
# Options:
#   --game FOLDER     the game folder (default D:\SquareEnix\FINAL FANTASY XIV - A Realm Reborn\game)
#   --mod-dir FOLDER  Penumbra mod folder (default D:\SquareEnix)
#   --mod-name NAME   mod to create or update (default "Luminis Vanilla Materials")
#   --what LIST       eyes,hair (default both)
#   --color/--light/--misc/--detail/--highlight R,G,B,A   settings (same as mtrl_luminis.py)
import argparse, json, pathlib, sys, uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mtrl_luminis as ml
from sqpack import SqPack

GAME = r"D:\SquareEnix\FINAL FANTASY XIV - A Realm Reborn\game"
MOD_DIR = r"D:\SquareEnix"
RACES = [f"c{r:02d}{s:02d}" for r in range(1, 19) for s in (1, 4)]   # adults (01) and children (04)
KNOWN = "chara/human/c0101/obj/face/f0001/material/mt_c0101f0001_iri_a.mtrl"

def eye_paths():
    for race in RACES:
        for face in range(1, 301):
            for v in "ab":
                yield f"chara/human/{race}/obj/face/f{face:04d}/material/mt_{race}f{face:04d}_iri_{v}.mtrl"

def hair_paths():
    for race in RACES:
        for hair in range(1, 1000):
            for var in range(1, 6):
                for v in "ab":
                    yield f"chara/human/{race}/obj/hair/h{hair:04d}/material/v{var:04d}/mt_{race}h{hair:04d}_hir_{v}.mtrl"

def four(s):
    v = tuple(float(x) for x in s.split(","))
    if len(v) != 4:
        raise argparse.ArgumentTypeError("needs exactly four comma-separated numbers")
    return v

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=GAME)
    ap.add_argument("--mod-dir", default=MOD_DIR)
    ap.add_argument("--mod-name", default="Luminis Vanilla Materials")
    ap.add_argument("--what", default="eyes,hair")
    for k in ml.NAMES:
        ap.add_argument(f"--{k}", type=four)
    a = ap.parse_args()
    values = {k: getattr(a, k) for k in ml.NAMES if getattr(a, k) is not None}
    what = {x.strip() for x in a.what.split(",")}

    print("Reading the game's chara archive index...")
    pack = SqPack(a.game, "chara")
    if not pack.exists(KNOWN):
        sys.exit("STOPPED: couldn't find a known vanilla material in the archive; the archive format or "
                 "hashing differs from what this tool expects. Nothing was written.")
    first = pack.read(KNOWN)
    if ml.shader_package_name(first) != "iris.shpk":
        sys.exit("STOPPED: read a known material but it didn't decode correctly. Nothing was written.")

    mod = pathlib.Path(a.mod_dir) / a.mod_name
    mod.mkdir(parents=True, exist_ok=True)
    meta_path = mod / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    else:
        meta = {"FileVersion": 4, "Identifier": str(uuid.uuid4()), "Name": a.mod_name,
                "Author": "Wyse", "Description": "Vanilla eye and hair materials with Luminis glow settings."}
    files = meta.setdefault("DefaultData", {}).setdefault("Files", {})

    found = {"eyes": 0, "hair": 0}
    groups = []
    if "eyes" in what:
        groups.append(("eyes", eye_paths(), "iris.shpk"))
    if "hair" in what:
        groups.append(("hair", hair_paths(), "hair.shpk"))
    for label, paths, shader in groups:
        print(f"Scanning {label}...")
        for gp in paths:
            if not pack.exists(gp):
                continue
            try:
                data = pack.read(gp)
                if (ml.shader_package_name(data) or "").lower() != shader:
                    continue
                new, _, _ = ml.apply_luminis(data, values)
            except Exception as e:
                print(f"  skipped {gp}: {e}")
                continue
            rel = pathlib.PureWindowsPath(*gp.split("/"))
            dest = mod / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(new)
            files[gp] = str(rel)
            found[label] += 1
        print(f"  {found[label]} {label} materials")

    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {sum(found.values())} materials into {mod}")
    print("In Penumbra: Settings > Rediscover Mods, enable the mod, and give it a lower priority than Luminis Dev.")

if __name__ == "__main__":
    main()
