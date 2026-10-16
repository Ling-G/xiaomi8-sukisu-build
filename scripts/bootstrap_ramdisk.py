"""Add a pinned userspace bootstrap to this device's gzip/newc ramdisk."""
import gzip
import hashlib
import stat
from pathlib import Path

KSUD_SHA256 = "9f57222b06222f461bbb69b24e40a293e34708eeb7b1bbb065110651f7b9c991"


def unpack_newc(data):
    entries = []
    pos = 0
    while True:
        start = pos
        header = data[pos:pos + 110]
        if len(header) != 110 or header[:6] != b"070701":
            raise ValueError("Expected an uncompressed newc CPIO archive")
        fields = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
        size, namesize = fields[6], fields[11]
        pos += 110
        rawname = data[pos:pos + namesize]
        if not rawname.endswith(b"\0"):
            raise ValueError("Invalid CPIO filename")
        name = rawname[:-1].decode("utf-8")
        pos = (pos + namesize + 3) & ~3
        content = data[pos:pos + size]
        if len(content) != size:
            raise ValueError("Truncated CPIO content")
        pos = (pos + size + 3) & ~3
        entries.append((name, fields, content, data[start:pos]))
        if name == "TRAILER!!!":
            if any(data[pos:]):
                raise ValueError("Unexpected data after CPIO trailer")
            return entries


def entry(name, fields, content):
    fields = list(fields)
    name = name.encode() + b"\0"
    fields[6], fields[11], fields[12] = len(content), len(name), 0
    data = b"070701" + b"".join(f"{n:08x}".encode() for n in fields) + name
    data += bytes(-len(data) % 4)
    data += content
    return data + bytes(-len(data) % 4)


def add_bootstrap(ramdisk, ksud_path):
    payload = ksud_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != KSUD_SHA256:
        raise ValueError("Expected the verified official ARM64 ksud 4.2.0 binary")
    entries = unpack_newc(gzip.decompress(ramdisk))
    names = [n for n, _, _, _ in entries]
    if names.count("init") != 1:
        raise ValueError("Unexpected stock first-stage init layout")
    if any(n in names for n in ("dipper-ksud", "dipper-bootstrap.sh")):
        raise ValueError("Bootstrap already exists")
    script = Path(__file__).with_name("bootstrap-ksud.sh").read_bytes()
    if b"\r" in script:
        raise ValueError("Bootstrap shell script must use LF line endings")
    result = b""
    for name, fields, content, raw in entries:
        if name == "TRAILER!!!":
            for ino, filename, data in (
                (0x100001, "dipper-ksud", payload),
                (0x100002, "dipper-bootstrap.sh", script),
            ):
                result += entry(filename, [ino, stat.S_IFREG | 0o700, 0, 0, 1, 0,
                                          0, 0, 0, 0, 0, 0, 0], data)
            result += raw
        else:
            result += raw
    # Independently parse the generated archive before putting it in a boot image.
    checked = {n: c for n, _, c, _ in unpack_newc(result)}
    assert checked["dipper-ksud"] == payload
    for name, _, content, _ in entries:
        if name != "TRAILER!!!":
            assert checked[name] == content, name
    return gzip.compress(result, mtime=0)
