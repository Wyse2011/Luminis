# make_glow_mod.py - turn a painted glow layer into a standalone, toggleable Luminis glow mod.
#
# Usage (from D:\luminis):
#   python tools\make_glow_mod.py --name "My Tattoo - Glow" --layer textures\my_glow.png ^
#       --material reference\skin\mt_c1701b0001_b.mtrl chara/human/c1701/obj/body/b0001/material/v0001/mt_c1701b0001_b.mtrl
#
# The glow layer is an image where only the glowing parts are painted (in any colors) and
# everything else is transparent: its colors become the glow colors, its transparency decides
# where it glows. PNG, TGA or an already-converted .tex all work.
#
# Creates a new Penumbra mod (in D:\SquareEnix by default) containing a Luminis copy of each given
# material with the glow layer attached, plus the glow layer texture. Enable it ABOVE your body
# mod and tattoo mod; switch it off to turn the glow off. Requires the Luminis mod.
#
# Options:
#   --material FILE GAME_PATH   a material to make glow (repeatable; every one gets the same layer).
#                               Export it from Penumbra's On-Screen tab; GAME_PATH is its left column.
#   --layer-path GAME_PATH      where the glow layer goes in-game (default: next to the material's textures)
#   --intensity N               glow brightness (default 1.5)
#   --mode dark|always|light    when it glows (default dark)
#   --tint R,G,B                multiplies the glow colors (default 1,1,1 = the layer's own colors)
#   --area-mix N                0 = react to light on the skin, 1 = to the area's brightness (default 0.5)
#   --mod-dir FOLDER            Penumbra mod folder (default D:\SquareEnix)
#   --update                    allow updating an existing glow mod with the same name
import argparse, json, pathlib, shutil, struct, sys, uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mtrl_luminis as ml

MOD_DIR = r"D:\SquareEnix"
MODES = {"always": 0.0, "dark": 1.0, "light": 2.0}
TEX_2D = 0x00800000
TEX_B8G8R8A8 = 0x1450

def fail(msg):
    sys.exit(f"STOPPED: {msg}\nNothing was written.")

def image_to_tex(path):
    """Uncompressed B8G8R8A8 .tex with a full mip chain, from any image Pillow can read."""
    try:
        from PIL import Image
    except ImportError:
        fail("reading PNG/TGA needs Pillow: run  pip install pillow  (or convert the image to .tex in "
             "Penumbra's Textures tab and pass the .tex instead)")
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    if w & (w - 1) or h & (h - 1):
        fail(f"{path} is {w}x{h}; texture sizes must be powers of two (for example 2048x2048, same as the body texture)")
    mips, cur = [], img
    while True:
        r, g, b, a = cur.split()
        mips.append(Image.merge("RGBA", (b, g, r, a)).tobytes())   # game order: B, G, R, A
        if cur.size == (1, 1) or len(mips) == 13:
            break
        cur = cur.resize((max(1, cur.size[0] // 2), max(1, cur.size[1] // 2)), Image.BOX)
    offsets, pos = [], 80
    for m in mips:
        offsets.append(pos); pos += len(m)
    header = struct.pack("<IIHHHBB", TEX_2D, TEX_B8G8R8A8, w, h, 1, len(mips), 0)
    header += struct.pack("<3I", 0, min(1, len(mips) - 1), min(2, len(mips) - 1))
    header += struct.pack("<13I", *(offsets + [0] * (13 - len(offsets))))
    return header + b"".join(mips)

def norm(p):
    p = p.strip().replace("\\", "/").lower()
    if ":" in p or p.startswith("/") or "/" not in p:
        fail(f"'{p}' doesn't look like a game path")
    return p

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--layer", required=True)
    ap.add_argument("--material", nargs=2, action="append", metavar=("FILE", "GAME_PATH"), required=True)
    ap.add_argument("--layer-path")
    ap.add_argument("--intensity", type=float, default=1.5)
    ap.add_argument("--mode", choices=MODES, default="dark")
    ap.add_argument("--tint", default="1,1,1")
    ap.add_argument("--area-mix", type=float, default=0.5)
    ap.add_argument("--mod-dir", default=MOD_DIR)
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    tint = tuple(float(x) for x in a.tint.split(","))
    if len(tint) != 3:
        fail("--tint needs three numbers, like 1,0.5,0")

    # Glow layer texture
    layer = pathlib.Path(a.layer)
    if not layer.is_file():
        fail(f"{layer} not found")
    tex = layer.read_bytes() if layer.suffix.lower() == ".tex" else image_to_tex(layer)

    # Materials
    mats = []
    for file, gp in a.material:
        data = pathlib.Path(file).read_bytes() if pathlib.Path(file).is_file() else fail(f"{file} not found")
        shader = (ml.shader_package_name(data) or "").lower()
        if shader not in ml.GLOW_TEXTURE_SLOT:
            fail(f"{file} uses {shader or 'an unknown shader'}; glow layers work on skin and hair materials")
        mats.append((data, norm(gp), shader))
    first_gp = mats[0][1]
    stem = first_gp.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    folder = first_gp.rsplit("/material/", 1)[0] if "/material/" in first_gp else first_gp.rsplit("/", 1)[0]
    layer_gp = norm(a.layer_path) if a.layer_path else f"{folder}/texture/{stem}_luminis.tex"

    mod_name = a.name.strip()
    mod = pathlib.Path(a.mod_dir) / "".join(c for c in mod_name if c not in '<>:"/\\|?*').strip()
    if mod.exists() and not a.update:
        fail(f"{mod} already exists; use --update to replace its glow, or pick another --name")
    mod.mkdir(parents=True, exist_ok=True)

    files = {}
    def put(gp, payload):
        rel = pathlib.PureWindowsPath(*gp.split("/"))
        dest = mod / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(payload)
        files[gp] = str(rel)

    put(layer_gp, tex)
    for data, gp, shader in mats:
        area = 3.0 if shader == "hair.shpk" else 0.0      # hair: "Luminis texture"; skin: "Glow layer"
        values = {"color": (*tint, a.intensity),
                  "light": (0.02, 0.15, MODES[a.mode], 1.0),
                  "misc": (2.0, a.area_mix, area, 0.0)}    # color source 2 = the glow layer's colors
        new, _, result = ml.apply_luminis(data, values, layer_gp)
        put(gp, new)
        print(f"material  {gp}  ({shader}, intensity {a.intensity:g}, glows {a.mode})")
    print(f"layer     {layer_gp}  ({len(tex) / 1e6:.1f} MB)")

    meta_path = mod / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8-sig")) if meta_path.exists() else {
        "FileVersion": 4, "Identifier": str(uuid.uuid4()), "Name": mod_name, "Author": "Wyse",
        "Description": "Luminis glow layer. Requires the Luminis mod. Enable above the body mod and the "
                       "tattoo mod it belongs to; switch off to turn the glow off. Fine-tune the glow in "
                       "Penumbra's material editor (Luminis Glow section)."}
    meta.setdefault("DefaultData", {})["Files"] = files
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nCreated {mod}")
    print("In Penumbra: Settings > Rediscover Mods, enable it, and give it a higher priority than your body and tattoo mods.")

if __name__ == "__main__":
    main()
