# build_gear.py - build both gear shader packages: python tools\build_gear.py
# (characterlegacy.shpk: most gear, minions and mounts; character.shpk: newer ones). Takes a while.
import pathlib, subprocess, sys
b = str(pathlib.Path(__file__).with_name("build_luminis.py"))
for prof in ("characterlegacy", "character"):
    r = subprocess.call([sys.executable, b, prof])
    if r:
        sys.exit(r)
