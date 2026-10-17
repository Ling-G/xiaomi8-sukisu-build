"""Run only on a Linux/Android Python host after a separately verified build.

Tests the explicit /dev/vt_abi_probe endpoint, not the original VT executable.
"""
import ctypes as c
import errno
import fcntl
import os

class Request(c.Structure):
    _fields_ = [('pid', c.c_int32), ('reserved', c.c_uint32),
                ('addr', c.c_uint64), ('buffer', c.c_uint64), ('size', c.c_uint64)]

def invoke(fd, command, request):
    return fcntl.ioctl(fd, command, bytes(request))

def expect_error(code, action):
    try:
        action()
    except OSError as error:
        assert error.errno == code, error
    else:
        raise AssertionError(f'Expected errno {code}')

def main():
    source = c.create_string_buffer(b'VT ABI probe')
    dest = c.create_string_buffer(c.sizeof(source))
    request = Request(os.getpid(), 0, c.addressof(source), c.addressof(dest), c.sizeof(source))
    fd = os.open('/dev/vt_abi_probe', os.O_RDWR | os.O_CLOEXEC)
    try:
        assert invoke(fd, 0x02813449, request) == 0
        assert dest.raw == source.raw
        replacement = c.create_string_buffer(b'VT new value')
        request.buffer = c.addressof(replacement)
        request.size = c.sizeof(replacement)
        assert invoke(fd, 0x02813450, request) == 0
        assert source.raw == replacement.raw
        request.pid = -1
        expect_error(errno.EINVAL, lambda: invoke(fd, 0x02813449, request))
        request.pid = os.getpid()
        request.size = 65537
        expect_error(errno.E2BIG, lambda: invoke(fd, 0x02813449, request))
        expect_error(errno.EOPNOTSUPP, lambda: invoke(fd, 0x02813441, request))
        expect_error(errno.EINVAL, lambda: invoke(fd, 0, request))
    finally:
        os.close(fd)
    print('PASS: self read/write, invalid PID, size cap, unsupported and unknown commands; use native client for child-process tests')

if __name__ == '__main__':
    main()
