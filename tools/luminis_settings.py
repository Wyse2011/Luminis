# luminis_settings.py - export Luminis settings from a material, and import them into another.
#
# Double-click (or run without arguments) for a small window with Export / Import / Copy buttons.
# Or from the command line (from D:\luminis):
#   python tools\luminis_settings.py export OLD.mtrl settings.json
#   python tools\luminis_settings.py import settings.json NEW.mtrl [MORE.mtrl ...] [--no-textures]
#                                           [--only glow,animation,layer2,rows]
#   python tools\luminis_settings.py copy OLD.mtrl NEW.mtrl [MORE.mtrl ...] [same options]
#
# Settings files are plain JSON. Importing changes only Luminis settings (and, unless --no-textures,
# the glow layer paths); everything else in the material stays as it was. Each changed material is
# backed up first as NAME.mtrl.bak. In Penumbra, click Reload Mod afterwards, then redraw.
import argparse, json, pathlib, shutil, struct, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mtrl_luminis as ml

FORMAT = "luminis-settings"
SECTIONS = {
    "glow":      ["color", "light", "misc", "detail", "highlight"],
    "animation": ["anim", "animcolor", "animcolor3", "animcolor4"],
    "layer2":    ["l2color", "l2light", "l2anim", "l2animcolor", "l2animcolor3", "l2animcolor4"],
    "rows":      ["rows1", "rows2", "rows3", "rows4"],
}
LAYER_SLOTS = {"layer1": "g_SamplerLuminis", "layer2": "g_SamplerLuminis2"}
DUMMY = "common/graphics/texture/dummy.tex"


class SettingsError(Exception):
    pass


def glow_textures(d):
    """The texture paths bound to the two glow layer slots (None when unset)."""
    ver, fsize, dsize, ssize, shoff, tc, uvc, csc, addsz = struct.unpack_from("<IHHHHBBBB", d, 0)
    strings_at = 16 + 4 * (tc + uvc + csc)
    hdr = strings_at + ssize + addsz + dsize
    vsz, kc, cc, sc = struct.unpack_from("<HHHH", d, hdr)
    samps_at = hdr + 12 + 8 * kc + 8 * cc
    samplers = {struct.unpack_from("<I", d, samps_at + 12 * i)[0]: d[samps_at + 12 * i + 8] for i in range(sc)}
    out = {}
    for layer, slot in LAYER_SLOTS.items():
        tex_i = samplers.get(ml.name_id(slot))
        if tex_i is None:
            out[layer] = None
            continue
        off = struct.unpack_from("<H", d, 16 + 4 * tex_i)[0]
        path = d[strings_at + off:d.index(b"\0", strings_at + off)].decode()
        out[layer] = None if path == DUMMY else path
    return out


def read_settings(path):
    d = pathlib.Path(path).read_bytes()
    try:
        if not ml.has_luminis(d):
            raise SettingsError(f"{pathlib.Path(path).name} has no Luminis settings to export")
        values = ml.apply_luminis(d)[2]
    except ml.MaterialError as e:
        raise SettingsError(f"{pathlib.Path(path).name}: {e}")
    return {
        "format": FORMAT, "version": 1,
        "from": pathlib.Path(path).name,
        "shader": ml.shader_package_name(d),
        "settings": {k: [round(float(x), 6) for x in v] for k, v in values.items()},
        "glow_layers": glow_textures(d),
    }


def apply_settings(settings, target, sections=None, textures=True):
    """Write settings into a material file (backed up first). Returns a list of notes."""
    if settings.get("format") != FORMAT:
        raise SettingsError("not a Luminis settings file")
    target = pathlib.Path(target)
    d = target.read_bytes()
    notes = []
    shader = ml.shader_package_name(d)
    if settings.get("shader") and shader and settings["shader"].lower() != shader.lower():
        notes.append(f"{target.name}: settings came from {settings['shader']}, this material uses {shader}; "
                     "Glow area and Color source can mean different things there, so check them")
    keys = [k for s in (sections or SECTIONS) for k in SECTIONS[s]]
    values = {k: tuple(settings["settings"][k]) for k in keys if k in settings["settings"]}
    layers = settings.get("glow_layers") or {}
    t1 = layers.get("layer1") if textures else None
    t2 = layers.get("layer2") if textures else None
    try:
        new, _, _ = ml.apply_luminis(d, values, t1, t2)
    except ml.MaterialError as e:
        raise SettingsError(f"{target.name}: {e}")
    except SystemExit as e:    # the material tool stops with a message for unsupported shaders
        raise SettingsError(f"{target.name}: {e}")
    shutil.copy2(target, target.with_name(target.name + ".bak"))
    target.write_bytes(bytes(new))
    notes.append(f"{target.name}: {len(values)} settings" + (", glow layers" if (t1 or t2) else "") +
                 f" imported (backup: {target.name}.bak)")
    return notes


def parse_sections(text):
    if not text:
        return None
    wanted = [s.strip().lower() for s in text.split(",") if s.strip()]
    bad = [s for s in wanted if s not in SECTIONS]
    if bad:
        raise SettingsError(f"unknown section {', '.join(bad)} (choose from {', '.join(SECTIONS)})")
    return wanted


# ---------------------------------------------------------------- window

def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.title("Luminis Settings")
    root.resizable(False, False)
    pad = {"padx": 10, "pady": 4}
    tk.Label(root, text="Move Luminis settings from one material to another.",
             font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", **pad)

    sec_vars = {s: tk.BooleanVar(value=True) for s in SECTIONS}
    labels = {"glow": "Glow (color, mode, area, ...)", "animation": "Animation",
              "layer2": "Layer 2", "rows": "Color table rows (gear)"}
    box = tk.LabelFrame(root, text="What to import")
    box.grid(row=1, column=0, columnspan=2, sticky="we", **pad)
    for i, s in enumerate(SECTIONS):
        tk.Checkbutton(box, text=labels[s], variable=sec_vars[s]).grid(row=i // 2, column=i % 2, sticky="w", padx=6)
    tex_var = tk.BooleanVar(value=True)
    tk.Checkbutton(box, text="Glow layer texture paths", variable=tex_var).grid(row=2, column=0, sticky="w", padx=6)

    status = tk.Label(root, text="", justify="left", anchor="w", wraplength=440)
    status.grid(row=4, column=0, columnspan=2, sticky="we", **pad)
    mtrl_types = [("Materials", "*.mtrl"), ("All files", "*.*")]
    json_types = [("Luminis settings", "*.json"), ("All files", "*.*")]

    def chosen():
        secs = [s for s, v in sec_vars.items() if v.get()]
        if not secs and not tex_var.get():
            raise SettingsError("nothing selected to import")
        return secs, tex_var.get()

    def report(lines, ok=True):
        status.config(text="\n".join(lines), fg="#1a7f37" if ok else "#b42318")

    def do_export():
        src = filedialog.askopenfilename(title="Material to export from", filetypes=mtrl_types)
        if not src:
            return
        try:
            s = read_settings(src)
        except SettingsError as e:
            return report([str(e)], False)
        out = filedialog.asksaveasfilename(title="Save settings as", defaultextension=".json",
                                           initialfile=pathlib.Path(src).stem + ".luminis.json", filetypes=json_types)
        if out:
            pathlib.Path(out).write_text(json.dumps(s, indent=2))
            report([f"Exported {len(s['settings'])} settings from {pathlib.Path(src).name}",
                    f"to {pathlib.Path(out).name}"])

    def do_import(settings=None):
        try:
            secs, tex = chosen()
            if settings is None:
                src = filedialog.askopenfilename(title="Settings file to import", filetypes=json_types)
                if not src:
                    return
                settings = json.loads(pathlib.Path(src).read_text())
            targets = filedialog.askopenfilenames(title="Material(s) to import into", filetypes=mtrl_types)
            if not targets:
                return
            notes = []
            for t in targets:
                notes += apply_settings(settings, t, secs, tex)
            report(notes + ["In Penumbra: Reload Mod, then redraw."])
        except (SettingsError, json.JSONDecodeError, OSError) as e:
            report([str(e)], False)

    def do_copy():
        src = filedialog.askopenfilename(title="Material to copy settings from", filetypes=mtrl_types)
        if not src:
            return
        try:
            s = read_settings(src)
        except SettingsError as e:
            return report([str(e)], False)
        do_import(s)

    btns = tk.Frame(root)
    btns.grid(row=3, column=0, columnspan=2, **pad)
    for i, (text, cmd) in enumerate([("Export settings...", do_export), ("Import settings...", do_import),
                                     ("Copy material to material...", do_copy)]):
        tk.Button(btns, text=text, width=24, command=cmd).grid(row=0, column=i, padx=4)
    root.mainloop()


# ---------------------------------------------------------------- command line

def main():
    if len(sys.argv) == 1:
        return gui()
    ap = argparse.ArgumentParser(description="Export and import Luminis settings between materials.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("material"); e.add_argument("json")
    for name in ("import", "copy"):
        p = sub.add_parser(name)
        p.add_argument("source", help="settings .json" if name == "import" else "material to copy from")
        p.add_argument("targets", nargs="+")
        p.add_argument("--no-textures", action="store_true", help="keep each target's own glow layer paths")
        p.add_argument("--only", help="comma-separated sections: " + ",".join(SECTIONS))
    a = ap.parse_args()
    try:
        if a.cmd == "export":
            s = read_settings(a.material)
            pathlib.Path(a.json).write_text(json.dumps(s, indent=2))
            print(f"Exported {len(s['settings'])} settings from {pathlib.Path(a.material).name} to {a.json}")
            for layer, p in s["glow_layers"].items():
                print(f"  {layer}: {p or '(none)'}")
            return
        settings = (json.loads(pathlib.Path(a.source).read_text()) if a.cmd == "import"
                    else read_settings(a.source))
        sections = parse_sections(a.only)
        for t in a.targets:
            for note in apply_settings(settings, t, sections, not a.no_textures):
                print(note)
        print("In Penumbra: Reload Mod, then redraw.")
    except (SettingsError, json.JSONDecodeError, OSError) as e:
        sys.exit(f"STOPPED: {e}")


if __name__ == "__main__":
    main()
