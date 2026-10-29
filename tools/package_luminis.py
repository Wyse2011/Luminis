# package_luminis.py - build the release Luminis.pmp from the current build.
#
# Usage (from D:\luminis):
#   python tools\package_luminis.py [--version 1.0] [--author NAME (default Wyse)] [--website URL]
#
# Takes the patched shader packages from the Luminis Dev mod and the dev-kit files from
# D:\luminis\devkit, and writes release\Luminis_<version>_<game version>.pmp with a "Parts"
# option group (Eyes, Hair, Skin; all on by default). The package contains only shaders and
# dev-kits: nothing changes in-game until a material has Luminis settings.
# It refuses to package a shader that doesn't carry the Luminis parameters.
import argparse, json, pathlib, struct, sys, zipfile, zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
MOD = pathlib.Path(r"D:\SquareEnix\Luminis Dev")
def _latest_game_version():
    """The newest vanilla/<game version>/ folder (named after the game version it was taken from)."""
    folders = sorted(p.name for p in (ROOT / "vanilla").iterdir() if p.is_dir() and p.name[:4].isdigit()) \
        if (ROOT / "vanilla").exists() else []
    return folders[-1] if folders else "unknown"

GAME_VERSION = _latest_game_version()
PARTS = [
    ("Eyes", "iris", "Glow for eyes (iris.shpk): a natural glowing iris, glow layers, emissive masks of glow-editable eye mods."),
    ("Hair", "hair", "Glow for hair (hair.shpk): whole hair, highlights, main color, or glow layers."),
    ("Skin", "skin", "Glow for skin (skin.shpk): glow layers for tattoos. Works with TBSE, Bibo and other body mods."),
    ("Gear", "characterlegacy", "Glow for most gear, minions, mounts and weapons (characterlegacy.shpk)."),
    ("Gear (newer)", "character", "Glow for newer gear, minions, mounts and weapons (character.shpk)."),
]
OPTIONAL = {"characterlegacy", "character"}   # gear parts: included when built
DESCRIPTION = """Luminis: light-sensitive, multi-color glow for eyes, hair and skin, rebuilt for Dawntrail.

This mod replaces the eye, hair and skin shaders with Luminis versions. On its own it changes nothing: a material only glows when it has Luminis settings with an intensity above 0. Glow-enabled eye, hair, tattoo and body mods provide those settings.

Load order: give Luminis a HIGHER priority than body mods (TBSE, Bibo, ...) and any other mod that replaces iris.shpk, hair.shpk or skin.shpk. Turn a part off below if another mod's shader must win for that part.

Settings appear as "Luminis Glow" in Penumbra's material editor (Advanced Editing > Materials).

Built for game version {game}. After a game patch, wait for an updated Luminis before re-enabling."""

def luminis_id(name):
    return zlib.crc32(name.encode(), 0xFFFFFFFF) ^ 0xFFFFFFFF

def check_shpk(path):
    d = path.read_bytes()
    if d[:4] != b"ShPk":
        sys.exit(f"STOPPED: {path} isn't a shader package")
    blobs_off = struct.unpack_from("<I", d, 16)[0]
    if struct.pack("<I", luminis_id("g_LuminisColor")) not in d[:blobs_off]:
        sys.exit(f"STOPPED: {path} doesn't carry the Luminis parameters (still vanilla?). Rebuild it first.")
    if struct.pack("<I", luminis_id("g_LuminisRows1")) not in d[:blobs_off]:
        sys.exit(f"STOPPED: {path} is from an older Luminis build (no row settings). Rebuild it, so every part matches.")
    return d

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.0")
    ap.add_argument("--author", default="Wyse")
    ap.add_argument("--website", default="")
    a = ap.parse_args()

    files = {}
    options = []
    for label, name, desc in PARTS:
        shpk = MOD / "shader" / "sm5" / "shpk" / f"{name}.shpk"
        devkit = ROOT / "devkit" / f"{name}.json"
        if not shpk.exists():
            if name in OPTIONAL:
                print(f"  (skipping {label}: {shpk.name} not built yet; run build_gear.py to include it)")
                continue
            sys.exit(f"STOPPED: {shpk} not found; run build_{name}.py first")
        if not devkit.exists():
            sys.exit(f"STOPPED: {devkit} not found")
        files[f"{label}\\shader\\sm5\\shpk\\{name}.shpk"] = check_shpk(shpk)
        files[f"{label}\\penumbra\\shpk_devkit\\{name}.json"] = devkit.read_bytes()
        options.append({
            "Name": label,
            "Description": desc,
            "Priority": 0,
            "Files": {f"shader/sm5/shpk/{name}.shpk": f"{label}\\shader\\sm5\\shpk\\{name}.shpk",
                      f"penumbra/shpk_devkit/{name}.json": f"{label}\\penumbra\\shpk_devkit\\{name}.json"},
            "FileSwaps": {},
            "Manipulations": [],
        })

    meta = {"FileVersion": 3, "Name": "Luminis", "Author": a.author, "Version": a.version,
            "Website": a.website, "Description": DESCRIPTION.format(game=GAME_VERSION),
            "ModTags": ["Luminis", "Glow", "Shader"]}
    default = {"Version": 0, "Files": {}, "FileSwaps": {}, "Manipulations": []}
    group = {"Version": 0, "Name": "Parts", "Description": "Which shaders Luminis replaces.",
             "Priority": 0, "Type": "Multi", "DefaultSettings": (1 << len(options)) - 1, "Options": options}

    out = ROOT / "release" / f"Luminis_{a.version}_{GAME_VERSION}.pmp"
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("meta.json", json.dumps(meta, indent=2))
        z.writestr("default_mod.json", json.dumps(default, indent=2))
        z.writestr("group_001_parts.json", json.dumps(group, indent=2))
        for rel, data in files.items():
            z.writestr(rel.replace("\\", "/"), data)
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    for o in options:
        print(f"  {o['Name']}: {next(iter(o['Files']))} + dev-kit")
    print("\nTo test: disable Luminis Dev, import the .pmp in Penumbra (Mods > Import), enable it, restart the game.")

if __name__ == "__main__":
    main()
