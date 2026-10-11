# build_iris.py - shortcut for: python tools\build_luminis.py iris [INDEX ...]
import pathlib, subprocess, sys
sys.exit(subprocess.call([sys.executable, str(pathlib.Path(__file__).with_name("build_luminis.py")), "iris"] + sys.argv[1:]))
