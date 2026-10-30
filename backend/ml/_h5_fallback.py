"""Minimal read-only HDF5 (superblock v0, v1 object headers, contiguous float32) reader.
Only for inspecting the supplied Keras weights file in a sandbox without h5py."""
import struct, numpy as np

class H5:
    def __init__(self, path):
        with open(path, "rb") as fh:
            self.d = fh.read()
        d = self.d
        assert d[:8] == b"\x89HDF\r\n\x1a\n" and d[8] == 0
        self.base = struct.unpack_from("<Q", d, 24)[0]
        root_ohdr = struct.unpack_from("<Q", d, 56 + 8)[0]  # root symtab entry: name_off(8) ohdr(8)
        self.root = root_ohdr
        self.datasets = {}
        self._walk(root_ohdr, "")

    def _messages(self, addr):
        d = self.d
        ver, _, nmsg = struct.unpack_from("<BBH", d, addr)
        hsize = struct.unpack_from("<I", d, addr + 8)[0]
        msgs, blocks = [], [(addr + 16, hsize)]
        while blocks:
            pos, size = blocks.pop(0)
            end = pos + size
            while pos + 8 <= end:
                mtype, msize, flags = struct.unpack_from("<HHB", d, pos)
                body = pos + 8
                if mtype == 0x10:  # continuation
                    off, ln = struct.unpack_from("<QQ", d, body)
                    blocks.append((off, ln))
                elif mtype != 0:
                    msgs.append((mtype, body, msize))
                pos = body + msize
        return msgs

    def _walk(self, addr, path):
        msgs = self._messages(addr)
        types = {m[0] for m in msgs}
        if 0x11 in types:  # symbol table => group
            body = [m for m in msgs if m[0] == 0x11][0][1]
            btree, heap = struct.unpack_from("<QQ", self.d, body)
            heap_data = struct.unpack_from("<Q", self.d, heap + 24)[0]
            for name, child in self._group_entries(btree, heap_data):
                self._walk(child, path + "/" + name)
        elif 0x08 in types:  # dataset
            shape = self._shape([m for m in msgs if m[0] == 0x01][0][1])
            lay = [m for m in msgs if m[0] == 0x08][0][1]
            ver, cls = struct.unpack_from("<BB", self.d, lay)
            assert ver == 3 and cls == 1, f"unsupported layout v{ver} class {cls}"
            a, sz = struct.unpack_from("<QQ", self.d, lay + 2)
            n = int(np.prod(shape)) if shape else 1
            arr = np.frombuffer(self.d, dtype="<f4", count=n, offset=a).reshape(shape)
            self.datasets[path] = arr.copy()

    def _shape(self, body):
        ver, rank, flags = struct.unpack_from("<BBB", self.d, body)
        off = body + (8 if ver == 1 else 4)
        return tuple(struct.unpack_from("<Q", self.d, off + 8 * i)[0] for i in range(rank))

    def _group_entries(self, btree, heap_data):
        d = self.d
        sig, ntype, level, nused = struct.unpack_from("<4sBBH", d, btree)
        assert sig == b"TREE"
        pos = btree + 24
        out = []
        for i in range(nused):
            pos += 8  # key
            child = struct.unpack_from("<Q", d, pos)[0]; pos += 8
            if level > 0:
                out += self._group_entries(child, heap_data)
            else:
                s, v, _, nsym = struct.unpack_from("<4sBBH", d, child)
                assert s == b"SNOD"
                p = child + 8
                for _ in range(nsym):
                    name_off, ohdr = struct.unpack_from("<QQ", d, p)
                    end = d.index(b"\0", heap_data + name_off)
                    out.append((d[heap_data + name_off:end].decode(), ohdr))
                    p += 40
        return out

if __name__ == "__main__":
    import sys
    h = H5(sys.argv[1])
    for k, v in h.datasets.items():
        u = np.unique(v)
        print(f"{k:55s} {str(v.shape):14s} min={v.min():+.4f} max={v.max():+.4f} mean={v.mean():+.4f} uniq={len(u)}")
