# magenta_batch.py - make "magenta test" versions of exported pixel shader blobs.
#
# Usage (from D:\luminis):
#   python tools\magenta_batch.py blobs\iris\composite_opaque compiled\iris\magenta
#
# For every ps_<N>.dxbc in the input folder it disassembles the shader, forces the
# color output to magenta just before each 'ret', reassembles it with the original
# shader's signatures (--copy-reflection), and saves ps_<N>_magenta.dxbc to the
# output folder. Originals are never modified.
import pathlib, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
DECOMPILER = ROOT / "tools" / "3dmigoto" / "cmd_Decompiler.exe"
MAGENTA = "mov o0.xyz, l(1.000000, 0.000000, 1.000000, 0.000000)\n"

def run(args, cwd):
    r = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError((r.stdout + r.stderr).strip())

def snapshot(folder):
    return {p.name: p.stat().st_mtime for p in folder.iterdir()}

def main():
    src_dir = pathlib.Path(sys.argv[1]).resolve()
    out_dir = pathlib.Path(sys.argv[2]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    blobs = sorted(src_dir.glob("ps_*.dxbc"))
    if not blobs:
        sys.exit(f"No ps_*.dxbc files found in {src_dir}")
    for blob in blobs:
        work = out_dir / "_work" / blob.stem
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        try:
            shutil.copy2(blob, work / blob.name)
            run([DECOMPILER, "-d", blob.name], work)
            asm = work / f"{blob.stem}.asm"
            if not asm.exists():
                raise RuntimeError("disassembly (.asm) was not produced")
            lines = asm.read_text().splitlines(keepends=True)
            patched, count = [], 0
            for line in lines:
                if line.strip() == "ret":
                    patched.append(MAGENTA)
                    count += 1
                patched.append(line)
            if count == 0:
                raise RuntimeError("no 'ret' instruction found")
            asm.write_text("".join(patched))
            before = snapshot(work)
            time.sleep(1.1)  # so a rewritten file gets a newer timestamp
            run([DECOMPILER, "-a", "--copy-reflection", blob, asm.name], work)
            after = snapshot(work)
            produced = [work / n for n, t in after.items()
                        if not n.endswith(".asm") and (n not in before or t > before[n])]
            if len(produced) != 1:
                raise RuntimeError(f"could not identify assembled output: {sorted(after)}")
            shutil.copy2(produced[0], out_dir / f"{blob.stem}_magenta.dxbc")
            print(f"ok    {blob.name}  ({count} ret patched, assembler wrote {produced[0].name})")
        except Exception as e:
            print(f"FAIL  {blob.name}: {e}")

if __name__ == "__main__":
    main()
