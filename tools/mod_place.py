# mod_place.py - put files into the Luminis Dev mod at their game paths and register the redirections.
#
# Usage (from D:\luminis):
#   python tools\mod_place.py file SOURCE GAME_PATH [SOURCE GAME_PATH ...]
#       Copy each file into the mod at its game path and redirect that game path to it.
#
#   python tools\mod_place.py material MTRL GAME_PATH [--textures FOLDER]
#       Place a material, then read the texture paths stored inside it and place every
#       matching texture found in FOLDER (default: the material's own folder) automatically.
#
#   python tools\mod_place.py list
#       Show the mod's current redirections.
#
# Options: --mod "D:\SquareEnix\Luminis Dev" to target a different mod folder.
# Edits the mod's default option (meta.json in current Penumbra, default_mod.json in older ones;
# a .luminis.bak backup is saved first). Afterwards, click
# Reload Mod for the mod in Penumbra so it picks up the changes, before editing it there.
import argparse, json, pathlib, re, shutil, struct, sys

DEFAULT_MOD = r"D:\SquareEnix\Luminis Dev"
GAME_PATH = re.compile(r"^[a-z0-9_]+(/[a-z0-9_.\-]+)+$")

def fail(msg):
    sys.exit(f"STOPPED: {msg}")

def norm_game_path(p):
    p = p.strip().replace("\\", "/").lower()
    if not GAME_PATH.match(p) or ":" in p or p.startswith("/"):
        fail(f"'{p}' doesn't look like a game path (expected something like chara/human/c1701/...)")
    return p

def load_container(mod):
    """Returns (file path, whole json, default-option container dict).
    Newer Penumbra keeps everything in meta.json under "DefaultData"; older versions use
    a separate default_mod.json."""
    meta = mod / "meta.json"
    legacy = mod / "default_mod.json"
    if legacy.exists():
        whole = json.loads(legacy.read_text(encoding="utf-8-sig"))
        container = whole
        path = legacy
    elif meta.exists():
        whole = json.loads(meta.read_text(encoding="utf-8-sig"))
        if whole.get("FileVersion", 0) < 4:
            fail("meta.json is an old format without DefaultData and there's no default_mod.json; open the mod in Penumbra once so it updates, then retry")
        container = whole.setdefault("DefaultData", {})
        path = meta
    else:
        fail(f"no meta.json in {mod}; is --mod pointing at the Penumbra mod folder?")
    if container.get("Files") is None:
        container["Files"] = {}
    return path, whole, container

def save_container(path, whole):
    shutil.copy2(path, path.with_name(path.name + ".luminis.bak"))
    path.write_text(json.dumps(whole, indent=2, ensure_ascii=False), encoding="utf-8")

def place(mod, data, source, game_path):
    source = pathlib.Path(source)
    if not source.is_file():
        fail(f"{source} not found")
    game_path = norm_game_path(game_path)
    rel = pathlib.PureWindowsPath(*game_path.split("/"))
    dest = mod / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)
    old = data["Files"].get(game_path)
    data["Files"][game_path] = str(rel)
    note = "" if old in (None, str(rel)) else f"  (was {old})"
    print(f"placed  {game_path}{note}")

def material_textures(mtrl):
    d = pathlib.Path(mtrl).read_bytes()
    ver, fsize, dsize, ssize, shoff, tc, uvc, csc, addsz = struct.unpack_from("<IHHHHBBBB", d, 0)
    if ver != 0x01030000:
        fail(f"{mtrl} isn't a material file this tool understands")
    strings_at = 16 + 4 * (tc + uvc + csc)
    out = []
    for i in range(tc):
        off = struct.unpack_from("<H", d, 16 + 4 * i)[0]
        end = d.index(b"\0", strings_at + off)
        out.append(d[strings_at + off:end].decode())
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["file", "material", "list"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--mod", default=DEFAULT_MOD)
    ap.add_argument("--textures")
    a = ap.parse_args()
    mod = pathlib.Path(a.mod)
    path, whole, data = load_container(mod)

    if a.command == "list":
        for gp, rel in sorted(data["Files"].items()):
            print(f"{gp}  ->  {rel}")
        print(f"\n{len(data['Files'])} redirections in the default option")
        return

    if a.command == "file":
        if not a.args or len(a.args) % 2:
            fail("give pairs of SOURCE GAME_PATH")
        for src, gp in zip(a.args[0::2], a.args[1::2]):
            place(mod, data, src, gp)

    if a.command == "material":
        if len(a.args) != 2:
            fail("give MTRL GAME_PATH")
        mtrl, gp = a.args
        place(mod, data, mtrl, gp)
        folder = pathlib.Path(a.textures) if a.textures else pathlib.Path(mtrl).parent
        for tex in material_textures(mtrl):
            if tex.startswith("~"):
                print(f"skip    {tex}  (texture embedded in the material's own folder)")
                continue
            name = tex.rsplit("/", 1)[-1]
            candidates = [p for p in folder.iterdir() if p.name.lower() == name.lower()]
            if candidates:
                place(mod, data, candidates[0], tex)
            else:
                print(f"missing {tex}  (no {name} in {folder}; left as the game's or another mod's copy)")

    save_container(path, whole)
    print("\nSaved. In Penumbra, click Reload Mod for this mod now, before editing it there.")

if __name__ == "__main__":
    main()
