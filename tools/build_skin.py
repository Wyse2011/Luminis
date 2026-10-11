# build_skin.py - shortcut for: python tools\build_luminis.py skin [INDEX ...]
import pathlib, subprocess, sys
sys.exit(subprocess.call([sys.executable, str(pathlib.Path(__file__).with_name("build_luminis.py")), "skin"] + sys.argv[1:]))
