#!/usr/bin/env python3
"""Convert the pinned MiCode audio/WLAN sources to an in-tree builtin build."""
import argparse,json,re,shutil
from pathlib import Path

def replace_once(p,old,new):
    s=p.read_text(); assert s.count(old)==1,(str(p),s.count(old)); p.write_text(s.replace(old,new,1))

def prepare(k,w):
    audio=k/'techpack/audio'
    conf=audio/'config/sdm845auto.conf'
    s=conf.read_text(); modular=re.findall(r'^(CONFIG_\w+)=m$',s,re.M)
    assert len(modular)==13,len(modular)
    conf.write_text(re.sub(r'^(CONFIG_\w+)=m$',r'\1=y',s,flags=re.M))
    replace_once(audio/'Makefile','obj-y += asoc/\nobj-y += dsp/\nobj-y += ipc/\nobj-y += soc/\n',
                 'obj-y += soc/\nobj-y += ipc/\nobj-y += dsp/\nobj-y += asoc/\n')
    # Providers are registered before codec consumers and the sound card.
    p=audio/'asoc/Makefile';line='obj-$(CONFIG_SND_SOC_MACHINE_SDM845) += snd-soc-sdm845.o\n'
    replace_once(p,line,''); p.write_text(p.read_text()+'\n'+line)
    p=audio/'asoc/codecs/Makefile';s=p.read_text()
    names=['WCD9XXX_CODEC_CORE','SND_SOC_WCD9XXX_V2','SND_SOC_WCD_MBHC','SND_SOC_WCD_SPI','SND_SOC_WSA881X']
    lines=[]
    for name in names:
        hits=[l for l in s.splitlines(True) if re.match(r'obj-\$\(CONFIG_'+name+r'\)\s*\+=',l)]
        assert len(hits)==1,(name,hits); lines.append(hits[0]);s=s.replace(hits[0],'',1)
    p.write_text(''.join(lines)+'\n'+s)
    for name in ['qcacld-3.0','qca-wifi-host-cmn','fw-api']:
        shutil.copytree(w/name,k/'drivers/staging'/name)
    replace_once(k/'drivers/staging/qcacld-3.0/Kbuild',
                 'WLAN_ROOT := drivers/staging/qcacld-3.0',
                 'WLAN_ROOT := $(srctree)/drivers/staging/qcacld-3.0')
    p=k/'drivers/staging/Makefile';p.write_text(p.read_text()+'\nobj-$(CONFIG_QCA_CLD_WLAN) += qcacld-3.0/\n')
    replace_once(k/'drivers/staging/Kconfig','endif # STAGING',
                 'source "drivers/staging/qcacld-3.0/Kconfig"\n\nendif # STAGING')
    # Native builtin WLAN mode waits for boot_wlan after filesystem setup.
    # Android init uses the existing KSU domain to write only this trigger.
    # No policy relaxation, external module or ksud invocation is required.
    p=k/'drivers/kernelsu/runtime/ksud.c'
    for event in ['on nonencrypted','on property:vold.decrypt=trigger_restart_framework']:
        old='    "'+event+'\\n"\n'
        new=old+'    '+json.dumps('    exec u:r:ksu:s0 root -- /system/bin/sh -c "echo 1 > /sys/kernel/boot_wlan/boot_wlan"\n')+'\n'
        replace_once(p,old,new)
    report={'audio_builtin_options':modular,'wifi':'CONFIG_QCA_CLD_WLAN=y',
            'wifi_start':'Android init boot_wlan trigger after filesystem setup',
            'autoload_module_required':False,'status':'compilation and hardware validation required'}
    (k/'builtin-integration.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('kernel',type=Path);p.add_argument('wlan',type=Path)
    a=p.parse_args();prepare(a.kernel,a.wlan)
