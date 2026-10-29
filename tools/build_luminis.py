# build_luminis.py - build a Luminis shader package into the Luminis Dev mod.
#
# Usage (from D:\luminis):   python tools\build_luminis.py iris|hair|skin [INDEX ...]
#
# With no indices it finds and patches every final-color (composite) shader in the package, so
# every race, gender, face, body and hairstyle is covered (currently 16 eye, 160 hair, 128 skin).
# Steps: build each shader's Luminis version by assembly patching (luminis_asm.py), add the
# Luminis material constants to the vanilla package, give each built shader its extra texture
# (iris: eye color texture for the glow map; hair: the Luminis texture in the decal slot), and
# patch the result into the mod. Shaders that can't be patched stay vanilla and are listed.
# Restart the game afterwards.
import json, pathlib, shutil, struct, subprocess, sys, hashlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
MOD = pathlib.Path(r"D:\SquareEnix\Luminis Dev")
# Which pixel shaders get Luminis: every final-color (composite) shader, found by the
# resources it binds, so all races, genders, faces, bodies and hairstyles are covered.
PROFILE_RULES = {
    # eyes: opaque composite shaders read G-buffer 2 and the eye mask
    "iris": lambda r: {"g_SamplerGBuffer2", "g_SamplerMask.T"} <= r,
    # hair: composite shaders (opaque, semi-transparent, underwater) calculate hair color
    # themselves and read ambient and instance data; depth and G-buffer shaders don't
    "hair": lambda r: {"g_AmbientParam", "g_InstanceParameter", "g_CustomizeParameter",
                       "g_SamplerNormal.T", "g_SamplerMask.T", "g_PbrParameterCommon"} <= r,
    # skin: composite shaders read G-buffer 2 (bodies, faces and other skin types)
    "skin": lambda r: "g_SamplerGBuffer2" in r,
    # gear, minions, mounts, weapons: composite shaders compute the item's color themselves and read
    # ambient and instance data (G-buffer shaders don't)
    "characterlegacy": lambda r: {"g_AmbientParam", "g_InstanceParameter", "g_SamplerNormal.T",
                                  "g_PbrParameterCommon", "g_CommonParameter"} <= r,
    "character": lambda r: {"g_AmbientParam", "g_InstanceParameter", "g_SamplerNormal.T",
                            "g_PbrParameterCommon", "g_CommonParameter"} <= r,
}
PROFILES = PROFILE_RULES
# New material texture slots a profile needs declared in its shader package first.
PROFILE_DECLARE = {k: "g_SamplerLuminis,g_SamplerLuminis2" for k in ("skin", "iris", "hair", "characterlegacy", "character")}

def resource_names(blob):
    """Names of the resources a DXBC shader binds (from its reflection data)."""
    count = struct.unpack_from("<I", blob, 28)[0]
    for j in range(count):
        off = struct.unpack_from("<I", blob, 32 + 4 * j)[0]
        if blob[off:off + 4] == b"RDEF":
            c = blob[off + 8:]
            n, boff = struct.unpack_from("<II", c, 8)
            names = set()
            for b in range(n):
                name_off = struct.unpack_from("<I", c, boff + 32 * b)[0]
                names.add(c[name_off:c.index(b"\0", name_off)].decode())
            return names
    return set()

def discover(profile, blobs):
    found = []
    for p in sorted(blobs.glob("ps_*.dxbc"), key=lambda q: int(q.stem[3:])):
        if PROFILE_RULES[profile](resource_names(p.read_bytes())):
            found.append(int(p.stem[3:]))
    return found

def step(title, args, allow_fail=False):
    """Run one build step, showing its output live (so long steps visibly make progress)."""
    print(f"== {title}", flush=True)
    r = subprocess.run([str(a) for a in args])
    if r.returncode != 0 and not allow_fail:
        sys.exit(f"\n{title} failed; stopping. Nothing was patched into the mod.")
    return r.returncode

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in PROFILES:
        sys.exit("usage: python tools\\build_luminis.py iris|hair|skin|characterlegacy|character [INDEX ...]")
    profile = sys.argv[1]
    explicit = [int(x) for x in sys.argv[2:]]
    # The newest vanilla\<game version>\ folder that has this shader package (see luminis_game_extract.py).
    candidates = sorted((p for p in (ROOT / "vanilla").glob(f"*/{profile}.shpk") if p.parent.name[:4].isdigit()),
                        key=lambda p: p.parent.name)
    vanilla = candidates[-1] if candidates else ROOT / "vanilla" / "missing" / f"{profile}.shpk"
    print(f"Vanilla {profile}.shpk: {vanilla.parent.name}")
    blobs = ROOT / "blobs" / profile / "all"
    stage = ROOT / "compiled" / profile / "stage"
    out_dir = ROOT / "compiled" / profile / "luminis"
    if not vanilla.exists():
        sys.exit(f"{vanilla} not found")
    # Re-extract when the vanilla package changed (a game patch), so stale shaders are never reused.
    source_tag = blobs / "source.txt"
    source_id = f"{vanilla.parent.name} {hashlib.sha1(vanilla.read_bytes()).hexdigest()}"
    if blobs.exists() and (not source_tag.exists() or source_tag.read_text().strip() != source_id):
        print(f"Vanilla {profile}.shpk changed since the last extraction; re-extracting")
        shutil.rmtree(blobs)
    if not blobs.exists():
        step("Extract vanilla shaders", [sys.executable, TOOLS / "shpk_extract.py", vanilla, blobs])
        source_tag.write_text(source_id + "\n")
    indices = explicit or discover(profile, blobs)
    print(f"{len(indices)} {profile} shader(s) to patch" + ("" if explicit else " (every final-color variant, found automatically)"))
    if out_dir.exists():
        shutil.rmtree(out_dir)
    stage.mkdir(parents=True, exist_ok=True)

    step(f"Build Luminis {profile} shaders", [sys.executable, TOOLS / "luminis_asm.py", profile, out_dir] + indices)
    built = json.loads((out_dir / "bindings.json").read_text())
    step("Add material constants", [sys.executable, TOOLS / "shpk_add_params.py", vanilla, stage / "step0.shpk"])
    current = stage / "step0.shpk"
    if any(b["add_binding"] for b in built):
        declare = ["--declare", PROFILE_DECLARE[profile]] if profile in PROFILE_DECLARE else []
        step("Add extra texture bindings", [sys.executable, TOOLS / "shpk_add_texture.py", current,
             stage / "step1.shpk", "--bindings", out_dir / "bindings.json"] + declare)
        current = stage / "step1.shpk"
    target = MOD / "shader" / "sm5" / "shpk" / f"{profile}.shpk"
    step("Patch into mod", [sys.executable, TOOLS / "shpk_patch.py", current, target, blobs, out_dir]
         + [str(p) for p in sorted({b["ps"] for b in built})])
    built_ps = sorted({b["ps"] for b in built})
    missing = sorted(set(indices) - set(built_ps))
    print(f"\nDone: {len(built_ps)} of {len(indices)} {profile} shaders carry Luminis."
          + (f" Still vanilla: {missing}" if missing else ""))
    if not (MOD / "meta.json").exists() or f"shader/sm5/shpk/{profile}.shpk" not in (MOD / "meta.json").read_text():
        print(f"Note: register the shader in the mod once with:\n"
              f"  python tools\\mod_place.py file \"{target}\" shader/sm5/shpk/{profile}.shpk")
    print("Restart the game to load the new shader package.")

if __name__ == "__main__":
    main()
