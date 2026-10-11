# color_test.py - find the active iris composite shader in two game restarts.
#
# Each candidate shader gets its final color forced to a test color, so the color the eyes
# turn tells you which shader is active.
#
#   Round 1:  python tools\color_test.py round1
#             -> eyes turn CYAN or MAGENTA (opaque pass groups) or RED, GREEN, BLUE or
#                YELLOW (semi-transparent groups); a blend of two means both passes draw
#   Round 2:  python tools\color_test.py round2 red      (or any group color above)
#             -> eyes turn one of 8 colors, which names the exact shader
#
# Run from D:\luminis. Reads originals from blobs\iris\all, writes test blobs to
# compiled\iris\colortest, then patches the Luminis Dev iris.shpk via shpk_patch.py,
# always starting from the vanilla copy. Restart the game after each round.
import pathlib, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
DECOMPILER = ROOT / "tools" / "3dmigoto" / "cmd_Decompiler.exe"
VANILLA = ROOT / "vanilla" / "2026.09.15" / "iris.shpk"
MOD_SHPK = pathlib.Path(r"D:\SquareEnix\Luminis Dev\shader\sm5\shpk\iris.shpk")
ORIG_DIR = ROOT / "blobs" / "iris" / "all"
OUT_DIR = ROOT / "compiled" / "iris" / "colortest"

GROUPS = {   # all 48 composite candidates for the eye material
    # opaque composite pass
    "cyan":    [3, 12, 19, 28, 35, 44, 51, 60],
    "magenta": [64, 68, 72, 76, 80, 84, 88, 92],
    # semi-transparent composite pass
    "red":    [8, 11, 14, 15, 24, 27, 30, 31],
    "green":  [40, 43, 46, 47, 56, 59, 62, 63],
    "blue":   [66, 67, 70, 71, 74, 75, 78, 79],
    "yellow": [82, 83, 86, 87, 90, 91, 94, 95],
}
COLORS = {
    "red": (1, 0, 0), "green": (0, 1, 0), "blue": (0, 0, 1), "yellow": (1, 1, 0),
    "cyan": (0, 1, 1), "magenta": (1, 0, 1), "white": (1, 1, 1), "orange": (1, 0.4, 0),
}
ROUND2_ORDER = ["red", "green", "blue", "yellow", "cyan", "magenta", "white", "orange"]

def run(args, cwd=None):
    r = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stdout + r.stderr).strip())
    return r.stdout

def make_test_blob(n, rgb):
    work = OUT_DIR / "_work" / f"ps_{n}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    src = ORIG_DIR / f"ps_{n}.dxbc"
    shutil.copy2(src, work / src.name)
    run([DECOMPILER, "-d", src.name], work)
    asm = work / f"ps_{n}.asm"
    line = "mov o0.xyz, l(%f, %f, %f, 0.000000)\n" % rgb
    out = []
    for l in asm.read_text().splitlines(keepends=True):
        if l.strip() == "ret":
            out.append(line)
        out.append(l)
    asm.write_text("".join(out))
    before = {p.name: p.stat().st_mtime for p in work.iterdir()}
    time.sleep(1.1)
    run([DECOMPILER, "-a", "--copy-reflection", src, asm.name], work)
    produced = [p for p in work.iterdir() if not p.name.endswith(".asm")
                and (p.name not in before or p.stat().st_mtime > before[p.name])]
    if len(produced) != 1:
        raise RuntimeError(f"ps_{n}: could not identify assembled output")
    shutil.copy2(produced[0], OUT_DIR / f"ps_{n}_test.dxbc")

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("round1", "round2"):
        sys.exit("usage: python tools\\color_test.py round1 | round2 <cyan|magenta|red|green|blue|yellow>")
    if sys.argv[1] == "round1":
        plan = {n: COLORS[g] for g, ns in GROUPS.items() for n in ns}
        legend = {g: f"group {g}: shaders {', '.join('#%d' % n for n in ns)}" for g, ns in GROUPS.items()}
    else:
        group = sys.argv[2].lower() if len(sys.argv) > 2 else ""
        if group not in GROUPS:
            sys.exit("round2 needs a round 1 group color: cyan, magenta, red, green, blue or yellow")
        plan = {n: COLORS[c] for n, c in zip(GROUPS[group], ROUND2_ORDER)}
        legend = {c: f"shader #{n}" for n, c in zip(GROUPS[group], ROUND2_ORDER)}

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    for n, rgb in plan.items():
        make_test_blob(n, rgb)
        print(f"made  ps_{n}  color {rgb}")

    print(run([sys.executable, ROOT / "tools" / "shpk_patch.py", VANILLA, MOD_SHPK,
               ORIG_DIR, OUT_DIR] + [str(n) for n in plan]))
    print("Restart the game, then look at the eye color:")
    for color, meaning in legend.items():
        print(f"  {color:8s} -> {meaning}")

if __name__ == "__main__":
    main()
