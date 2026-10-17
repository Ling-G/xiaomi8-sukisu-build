#!/usr/bin/env python3
"""Compare vendor modules against the actual CRC table embedded in an ARM64 Image."""
import argparse,gzip,json,struct
from pathlib import Path

def sections(data):
    if data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Expected little-endian ELF64')
    offset=struct.unpack_from('<Q',data,40)[0]
    size,count,index=struct.unpack_from('<3H',data,58)
    entries=[struct.unpack_from('<IIQQQQIIQQ',data,offset+i*size) for i in range(count)]
    names=entries[index]
    def string(start):return data[start:data.index(b'\0',start)].decode()
    return {string(names[4]+s[0]):s for s in entries},entries,string

def imports(data):
    sec,_,_=sections(data)
    version=sec['__versions'];start,size=version[4:6]
    return {data[p+8:data.index(b'\0',p+8)].decode():struct.unpack_from('<Q',data,p)[0]
            for p in range(start,start+size,64)}

def exports(data):
    sec,allsec,string=sections(data)
    s=sec['.symtab'];names=allsec[s[6]]
    result={}
    for p in range(s[4],s[4]+s[5],s[9]):
        name,info,other,index,value,size=struct.unpack_from('<IBBHQQ',data,p)
        name=string(names[4]+name)
        if index==0xfff1 and name.startswith('__crc_'):result[name[6:]]=value
    return result

def kernel_crcs(image_path,map_path):
    image=gzip.decompress(image_path.read_bytes())
    addresses={p[2]:int(p[0],16) for line in map_path.read_text().splitlines() if len(p:=line.split())==3}
    base=addresses['_text'];kernel={};targets={}
    for name,address in addresses.items():
        if name.startswith('__kcrctab_'):
            offset=address-base
            if not 0<=offset<=len(image)-8:raise ValueError('CRC outside Image')
            symbol=name[len('__kcrctab_'):]
            kernel[symbol]=struct.unpack_from('<Q',image,offset)[0]
            targets[address]=symbol
    # CONFIG_RELOCATABLE keeps these values in R_AARCH64_RELATIVE addends.
    # Recover the normalized CRC before the boot-time relocation offset is added.
    start=addresses.get('__init_begin',base)-base
    end=min(addresses.get('__init_end',base+len(image))-base,len(image))
    needle=struct.pack('<Q',1027)
    pos=image.find(needle,max(start+8,8),end)
    while pos!=-1 and pos+16<=end:
        target=struct.unpack_from('<Q',image,pos-8)[0]
        if target in targets:
            kernel[targets[target]]=struct.unpack_from('<Q',image,pos+8)[0]
        pos=image.find(needle,pos+8,end)
    return kernel

def check(image_path,map_path,module_dir):
    kernel=kernel_crcs(image_path,map_path)
    modules={p.name:p.read_bytes() for p in sorted(module_dir.glob('*.ko'))}
    available=dict(kernel)
    for data in modules.values():
        for name,value in exports(data).items():available.setdefault(name,value)
    reports=[]
    for name,data in modules.items():
        required=imports(data)
        mismatch=[{'symbol':s,'expected':f'{v:08x}','actual':None if s not in available else f'{available[s]:08x}'}
                  for s,v in required.items() if available.get(s)!=v]
        reports.append({'module':name,'imports':len(required),'mismatches':mismatch})
    return {'kernel_module_layout_crc':f'{kernel.get("module_layout",0):08x}',
            'passed':all(not r['mismatches'] for r in reports),'modules':reports}

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('image',type=Path);p.add_argument('system_map',type=Path);p.add_argument('modules',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args();r=check(a.image,a.system_map,a.modules)
    if a.output:a.output.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({'passed':r['passed'],'module_layout':r['kernel_module_layout_crc'],
                      'modules':[{'name':m['module'],'imports':m['imports'],'mismatches':len(m['mismatches'])} for m in r['modules']]},indent=2))
    raise SystemExit(0 if r['passed'] else 1)
