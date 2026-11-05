"""Non-destructive removable-media inventory for Groovebox/sOS.

Enumerates whole devices and partitions separately, including mmcblkN[pM], sdXN,
filesystem/type/label/mount state, and boot/EFI hints. This module never formats,
repairs, mounts, or writes to a device; privileged actions remain in sOS's guarded
sos-removable-media helper.
"""
from __future__ import annotations
import json, os, re, shutil, subprocess
from pathlib import Path

_DEVICE_RE = re.compile(r"^(?:mmcblk\d+|sd[a-z]+|nvme\d+n\d+|vd[a-z]+)$")
_PART_RE = re.compile(r"^(?:mmcblk\d+p\d+|sd[a-z]+\d+|nvme\d+n\d+p\d+|vd[a-z]+\d+)$")

def _run(args):
    try:
        cp=subprocess.run(args,capture_output=True,text=True,timeout=3)
        return cp.stdout.strip() if cp.returncode == 0 else ""
    except Exception:
        return ""

def inventory():
    """Return a best-effort inventory; absent tools degrade gracefully."""
    rows=[]
    lsblk=shutil.which('lsblk')
    if lsblk:
        raw=_run([lsblk,'-J','-b','-o','NAME,PATH,TYPE,SIZE,FSTYPE,LABEL,UUID,MOUNTPOINTS,PARTFLAGS,PARTTYPE,RM,RO'])
        try: data=json.loads(raw)
        except Exception: data={}
        def visit(node,parent=None):
            name=str(node.get('name') or '')
            if not (_DEVICE_RE.match(name) or _PART_RE.match(name)): return
            kind=str(node.get('type') or '')
            flags=str(node.get('partflags') or '')
            parttype=str(node.get('parttype') or '')
            mounts=node.get('mountpoints') or ([node.get('mountpoint')] if node.get('mountpoint') else [])
            mounts=[str(x) for x in mounts if x]
            removable=(str(node.get('rm') or '0')=='1' or name.startswith('mmcblk') or (parent and parent.startswith('mmcblk')))
            rows.append({
                'name':name,'path':str(node.get('path') or '/dev/'+name),'type':kind,
                'parent':parent or '', 'bytes':int(node.get('size') or 0),
                'filesystem':str(node.get('fstype') or ''),'label':str(node.get('label') or ''),
                'uuid':str(node.get('uuid') or ''),'mountpoints':mounts,
                'partition_flags':flags,'partition_type':parttype,
                'bootable':bool('boot' in flags.lower() or 'esp' in parttype.lower() or 'efi' in parttype.lower()),
                'removable':bool(removable),'read_only':str(node.get('ro') or '0')=='1',
                'status':'mounted' if mounts else ('filesystem-present' if node.get('fstype') else 'no-filesystem'),
            })
            for child in node.get('children') or []: visit(child,name if kind=='disk' else (parent or name))
        for node in (data.get('blockdevices') or []): visit(node)
    # Always merge sysfs-only devices: lsblk can omit a freshly enumerated MMC
    # card while still returning the internal SSD, which previously suppressed
    # the fallback and made the inserted card look absent.
    base=Path('/sys/class/block')
    try: names=sorted(p.name for p in base.iterdir())
    except OSError: names=[]
    existing={r.get('path') for r in rows}
    for name in names:
        if not (_DEVICE_RE.match(name) or _PART_RE.match(name)): continue
        devpath='/dev/'+name
        if devpath in existing: continue
        part=(base/name/'partition').exists()
        parent=re.sub(r'p?\d+$','',name) if part else ''
        try: size=int((base/name/'size').read_text().strip())*512
        except Exception: size=0
        rows.append({'name':name,'path':devpath,'type':'part' if part else 'disk','parent':parent,'bytes':size,'filesystem':'','label':'','uuid':'','mountpoints':[],'partition_flags':'','partition_type':'','bootable':False,'removable':name.startswith('mmcblk') or name.startswith('sd'),'read_only':False,'status':'detected-metadata-limited'})
    return rows

def summarize():
    rows=inventory()
    return {'devices':rows,'device_count':sum(r['type']=='disk' for r in rows),'partition_count':sum(r['type']=='part' for r in rows),'bootable_partitions':[r for r in rows if r['type']=='part' and r['bootable']],'unmounted_partitions':[r for r in rows if r['type']=='part' and not r['mountpoints']]}
