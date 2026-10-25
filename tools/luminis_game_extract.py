# luminis_game_extract.py - pull vanilla shader packages straight from the game, and survey which
# shaders the game's monsters/minions/mounts (and gear) use. Read-only: never writes to the game.
#
# Usage (from D:\luminis):
#   python tools\luminis_game_extract.py [--game FOLDER] [--no-survey]
#
# 1. Extracts every character shader package that exists (character, characterlegacy, characterglass,
#    ..., plus iris, hair, skin) into vanilla\<game version>\.
# 2. Surveys materials of monsters (most minions and mounts), demihumans and equipment, and writes
#    vanilla\<game version>\shader_survey.json plus a summary of which shader packages they use.
import argparse, collections, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sqpack import SqPack
import mtrl_luminis as ml

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAME = r"D:\SquareEnix\FINAL FANTASY XIV - A Realm Reborn\game"
SHADERS = ["character", "characterlegacy", "characterglass", "characterstockings", "charactertattoo",
           "characterocclusion", "characterreflection", "charactertransparency", "characterinc",
           "characterscroll", "characterwater", "iris", "hair", "skin", "bgcolorchange"]

def game_version(game):
    p = pathlib.Path(game) / "ffxivgame.ver"
    return p.read_text().strip().split(".0000")[0] if p.exists() else "unknown"

def survey(chara, out):
    """Probe common material paths; count shader packages per category."""
    counts = {k: collections.Counter() for k in ("monster", "demihuman", "equipment")}
    examples = {}
    def probe(kind, path):
        if not chara.exists(path):
            return False
        try:
            shader = ml.shader_package_name(chara.read(path)) or "?"
        except Exception:
            shader = "unreadable"
        counts[kind][shader] += 1
        examples.setdefault(f"{kind}:{shader}", path)
        return True
    print("Surveying monsters (most minions and mounts)...")
    h = chara._hash
    for m in range(1, 10000):
        for b in range(1, 21):
            names = {letter: h(f"mt_m{m:04d}b{b:04d}_{letter}.mtrl".encode()) for letter in "abcd"}
            for v in range(1, 11):
                folder = f"chara/monster/m{m:04d}/obj/body/b{b:04d}/material/v{v:04d}"
                fh = h(folder.encode()) << 32
                for letter, nh in names.items():
                    if (fh | nh) in chara.entries:
                        probe("monster", f"{folder}/mt_m{m:04d}b{b:04d}_{letter}.mtrl")
        if m % 1000 == 0:
            print(f"  m{m:04d}... {sum(counts['monster'].values())} materials so far", flush=True)
    print("Surveying demihumans...")
    for d in range(1, 2000):
        for e in range(1, 11):
            for part in ("met", "top", "glv", "dwn", "sho"):
                for v in range(1, 4):
                    probe("demihuman", f"chara/demihuman/d{d:04d}/obj/equipment/e{e:04d}/material/v{v:04d}/mt_d{d:04d}e{e:04d}_{part}_a.mtrl")
    print("Surveying equipment (sample)...")
    for e in range(1, 1000):
        for part in ("met", "top", "glv", "dwn", "sho"):
            probe("equipment", f"chara/equipment/e{e:04d}/material/v0001/mt_c0101e{e:04d}_{part}_a.mtrl")
    summary = {k: dict(c.most_common()) for k, c in counts.items()}
    out.write_text(json.dumps({"counts": summary, "examples": examples}, indent=2))
    print("\nShader packages used:")
    for k, c in counts.items():
        total = sum(c.values())
        print(f"  {k} ({total} materials): " + ", ".join(f"{s} {n}" for s, n in c.most_common()))
    print(f"\nWrote {out}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=GAME)
    ap.add_argument("--no-survey", action="store_true")
    a = ap.parse_args()
    ver = game_version(a.game)
    dest = ROOT / "vanilla" / ver
    dest.mkdir(parents=True, exist_ok=True)
    print(f"Game version {ver}; writing to {dest}")
    shader = SqPack(a.game, "shader")
    got = []
    for name in SHADERS:
        gp = f"shader/sm5/shpk/{name}.shpk"
        if shader.exists(gp):
            data = shader.read(gp)
            if data[:4] != b"ShPk":
                print(f"  skipped {name}.shpk (didn't decode)")
                continue
            (dest / f"{name}.shpk").write_bytes(data)
            got.append(f"{name}.shpk ({len(data) / 1e6:.1f} MB)")
    print("Extracted: " + ", ".join(got) if got else "STOPPED: no shader packages found; check --game")
    if not got:
        sys.exit(1)
    if not a.no_survey:
        survey(SqPack(a.game, "chara"), dest / "shader_survey.json")

if __name__ == "__main__":
    main()
