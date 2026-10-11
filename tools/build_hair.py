# build_hair.py - shortcut for: python tools\build_luminis.py hair [INDEX ...]
import pathlib, subprocess, sys
sys.exit(subprocess.call([sys.executable, str(pathlib.Path(__file__).with_name("build_luminis.py")), "hair"] + sys.argv[1:]))
