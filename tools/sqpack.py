# sqpack.py - minimal read-only access to FFXIV's game archives (SqPack), for standard files
# such as materials (.mtrl). Used by luminis_vanilla.py. Never writes to the game folder.
import pathlib, struct, zlib

CATEGORIES = {"common": "00", "bgcommon": "01", "bg": "02", "cut": "03", "chara": "04",
              "shader": "05", "ui": "06", "sound": "07", "vfx": "08", "exd": "0a",
              "game_script": "0b", "music": "0c"}

def _jamcrc(b):
    return zlib.crc32(b) ^ 0xFFFFFFFF

class SqPack:
    def __init__(self, game_dir, category):
        self.root = pathlib.Path(game_dir) / "sqpack" / "ffxiv"
        cat = CATEGORIES[category]
        self.indexes = sorted(self.root.glob(f"{cat}????.win32.index"))
        if not self.indexes:
            raise FileNotFoundError(f"no {cat}*.win32.index in {self.root}")
        self.entries = {}   # hash -> (index file stem, dat id, offset)
        for idx in self.indexes:
            d = idx.read_bytes()
            if d[:6] != b"SqPack":
                raise ValueError(f"{idx} isn't a SqPack index")
            hdr = struct.unpack_from("<I", d, 0x0C)[0]
            data_off, data_size = struct.unpack_from("<II", d, hdr + 8)
            if data_size % 16 or data_off + data_size > len(d):
                raise ValueError(f"{idx}: unexpected index layout")
            for i in range(data_size // 16):
                h, data = struct.unpack_from("<QI", d, data_off + 16 * i)
                self.entries[h] = (idx.name[:-len(".index")], (data & 0b1110) >> 1, (data & ~0xF) * 8)
        self._hash = _jamcrc

    def _key(self, path):
        path = path.lower()
        folder, _, name = path.rpartition("/")
        return (self._hash(folder.encode()) << 32) | self._hash(name.encode())

    def exists(self, path):
        return self._key(path) in self.entries

    def read(self, path):
        stem, dat_id, offset = self.entries[self._key(path)]
        with open(self.root / f"{stem}.dat{dat_id}", "rb") as f:
            f.seek(offset)
            head = f.read(24)
            header_size, ftype, raw_size, _, _, blocks = struct.unpack("<IIIIII", head)
            if ftype != 2:
                raise ValueError(f"{path} isn't a standard file (type {ftype})")
            f.seek(offset + 24)
            infos = [struct.unpack("<IHH", f.read(8)) for _ in range(blocks)]
            out = bytearray()
            for block_off, _, _ in infos:
                f.seek(offset + header_size + block_off)
                bsize, _, csize, usize = struct.unpack("<IIII", f.read(16))
                if csize == 32000:
                    out += f.read(usize)
                else:
                    out += zlib.decompress(f.read(csize), -15)
            if len(out) != raw_size:
                raise ValueError(f"{path}: size mismatch after decompression")
            return bytes(out)
