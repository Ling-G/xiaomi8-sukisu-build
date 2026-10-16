"""Check the actual C header layout against the recovered DWARF evidence."""
from pathlib import Path
import ctypes as c
import json
import re

root = Path(__file__).resolve().parent
evidence = json.loads((root.parent / 'protocol-analysis/protocol-evidence.json').read_text(encoding='utf-8'))
header = (root / 'vt_protocol.h').read_text(encoding='utf-8')
types = {'__s32': c.c_int32, '__u32': c.c_uint32, '__u64': c.c_uint64,
         '__u8': c.c_uint8, 'float': c.c_float}
names = {'vt_copy_memory': '_COPY_MEMORY', 'vt_module_base': '_MODULE_BASE',
         'vt_hw_bp_info': '_HW_BP_INFO', 'vt_hwbp_hit_args': '_HWBP_HIT_ARGS',
         'vt_tracking_data': '_TRACKING_DATA'}
checked = 0
for name, body in re.findall(r'struct (\w+)\s*\{(.*?)\};', header, re.S):
    fields = []
    for declaration in body.split(';'):
        declaration = declaration.strip()
        if not declaration:
            continue
        typ, variables = declaration.split(None, 1)
        for var in variables.split(','):
            match = re.fullmatch(r'(\w+)((?:\[\d+\])*)', var.strip())
            assert match, declaration
            field_type = types[typ]
            dims = [int(n) for n in re.findall(r'\[(\d+)\]', match[2])]
            for length in reversed(dims):
                field_type = field_type * length
            fields.append((match[1], field_type))
    layout = type(name, (c.Structure,), {'_fields_': fields})
    original = evidence[names[name]]
    assert c.sizeof(layout) == original['size'], (name, c.sizeof(layout), original['size'])
    for member in original['members']:
        assert getattr(layout, member['name']).offset == member['offset'], (name, member)
        checked += 1
    print(f'{name}: size {c.sizeof(layout)}, all recovered member offsets match')

commands = {name: int(value, 16) for name, value in re.findall(r'#define (VT_\w+)\s+(0x[0-9a-fA-F]+)U', header)}
dispatch = evidence['dispatch_table']
for name, value in commands.items():
    assert hex(value) in dispatch, name
assert dispatch[hex(commands['VT_MEMORY_READ'])] == '0x734'
assert dispatch[hex(commands['VT_MEMORY_WRITE'])] == '0x790'
assert dispatch[hex(commands['VT_MODULE_BASE'])] == '0x7f0'
print(f'PASS: {checked} field offsets, 5 structure sizes, {len(commands)} command values')
