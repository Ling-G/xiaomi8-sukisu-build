#!/usr/bin/env python3
"""Host isolation tests. Requires bash and the two official release APKs.

Android package queries, app stop and SELinux labels are simulated. This is
not a device/SELinux compatibility test. No phone or real /data is accessed.
"""
import argparse
import hashlib
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('apk420', type=Path)
    p.add_argument('apk421', type=Path)
    p.add_argument('--bash', default='bash')
    a = p.parse_args()
    assert sha(a.apk420) == '4ca9810e6355fbff0bbe4bf5ce159808e64a40d85987a11894030cd990a6bdf3'
    assert sha(a.apk421) == 'c7f69280cf468e8415c585ff31f963d0147386831217a1e89b822afddc5f40ed'
    source = Path(__file__).with_name('bootstrap-ksud.sh').read_text()
    subprocess.run([a.bash, '-n'], input=source, text=True, check=True)
    with tempfile.TemporaryDirectory(prefix='dipper-manager-test-') as temp:
        root = Path(temp)
        # Ask bash for its own path notation (also works with Git Bash).
        posix = subprocess.check_output([a.bash, '-c', 'cd "$1" && pwd', '_', str(root)], text=True).strip()
        script = source.replace('/data/', posix + '/data/').replace('/dev/dipper-', posix + '/dev/dipper-')
        script = script.replace('export PATH=/system/bin:/system/xbin', f'export PATH="{posix}/bin:/usr/bin:/bin"')
        # The fixture prefix may contain spaces; validate only the device suffix.
        script = script.replace('case "$apk" in *[!', 'case "${apk#"' + posix + '"}" in *[!')
        fixture = root / 'fixture.sh'
        fixture.write_text(script, newline='\n')
        base = root / 'data/app/com.sukisu.ultra-test'
        lib = base / 'lib/arm64/libksud.so'
        lib.parent.mkdir(parents=True)
        (root / 'data/adb').mkdir(parents=True)
        (root / 'dev').mkdir()
        (root / 'bin').mkdir()
        commands = {
            'getprop': 'echo 1',
            'cmd': f'echo "package:{posix}/data/app/com.sukisu.ultra-test/base.apk"',
            'ls': 'echo "u:object_r:apk_data_file:s0 $2"',
            'chcon': f'[ ! -e "{posix}/fail-context" ]',
            'am': f'echo "$*" >> "{posix}/am.log"',
        }
        for name, body in commands.items():
            f = root / 'bin' / name
            f.write_text('#!/bin/sh\n' + body + '\n', newline='\n')
            subprocess.run([a.bash, '-c', 'chmod +x "$1"', '_', str(f)], check=True)
        member = 'lib/arm64-v8a/libksud.so'
        with zipfile.ZipFile(a.apk420) as z:
            payload = z.read(member)
        with zipfile.ZipFile(a.apk421) as z:
            original = z.read(member)
        fixed_sha = hashlib.sha256(payload).hexdigest()
        original_sha = hashlib.sha256(original).hexdigest()
        (root / 'dev/dipper-ksud').write_bytes(payload)
        shutil.copyfile(a.apk421, base / 'base.apk')
        lib.write_bytes(original)

        def run():
            return subprocess.run([a.bash, str(fixture), '--manager-check'], capture_output=True, timeout=30)

        (root / 'fail-context').touch()
        assert run().returncode != 0 and sha(lib) == original_sha
        (root / 'fail-context').unlink()
        assert run().returncode == 0 and sha(lib) == fixed_sha
        assert sha(root / 'data/adb/dipper-manager-compat/original-libksud.so') == original_sha
        stops = (root / 'am.log').read_bytes()
        assert run().returncode == 0 and sha(lib) == fixed_sha
        assert (root / 'am.log').read_bytes() == stops
        lib.write_bytes(original)
        disable = root / 'data/adb/dipper-manager-compat.disable'
        disable.touch()
        assert run().returncode == 0 and sha(lib) == original_sha
        disable.unlink()
        with (base / 'base.apk').open('ab') as f:
            f.write(b'unknown')
        assert run().returncode == 0 and sha(lib) == original_sha
        shutil.copyfile(a.apk421, base / 'base.apk')
        lib.write_bytes(b'unknown backend')
        assert run().returncode == 0 and lib.read_bytes() == b'unknown backend'
        lib.write_bytes(original)
        (root / 'bin/getprop').write_text('#!/bin/sh\necho 0\n', newline='\n')
        assert run().returncode == 0 and sha(lib) == original_sha
    print('PASS: failure containment, repair, backup, idempotency, disable, unknown APK/library, pre-boot guard')


if __name__ == '__main__':
    main()
