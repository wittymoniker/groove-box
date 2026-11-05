# GROOVEBOX_V35_22ZZ_R23R_DISCOVERED_ENDPOINTS_UCM_DMIC_ASPM_20261005
# GROOVEBOX_V35_22ZZ_R23P_BOOT_HARDWARE_INIT_20261004
# GROOVEBOX_V35_22ZZ_R23L_FIXED_PERFORMANCE_DEVICES_SOF_SDMMC_20261003
# GROOVEBOX_V35_22ZZ_R23N_HWUCM_CAPTURE_MSI_READER_20261004
#!/usr/bin/env python3
"""Disposable Groovebox hardware probe.

All expensive enumeration happens here so the GUI process never retains probe
threads, Qt multimedia enumerators or PortAudio discovery state.
"""
from __future__ import annotations
import glob, json, os, queue, sys, re, shutil, subprocess, threading, time
from pathlib import Path

def _nice():
    try: os.nice(10)
    except Exception: pass

def _record():
    audio=[]
    # R23p: boot chose and primed one capture PCM; expose it first so the fixed
    # Performance selector and Mic Level use the same route initialized at boot.
    try:
        bs=Path('/run/sos/audio-hardware.state')
        vals={}
        if bs.is_file():
            for line in bs.read_text(errors='replace').splitlines():
                if '=' in line:
                    k,v=line.split('=',1); vals[k.strip()]=v.strip()
        pcm=vals.get('capture_pcm','')
        if pcm:
            audio.append({'index':-3000,'name':(vals.get('card_id') or 'Internal')+' · Boot-initialized microphone',
                          'backend':'alsa','device':pcm,
                          'meta':{'backend':'alsa','alsa_device':pcm,'boot_initialized':True,'card':vals.get('card',''),
                                  'card_id':vals.get('card_id',''),'max_input_channels':int(vals.get('capture_channels') or 2),'capture_channels':int(vals.get('capture_channels') or 2),'default_samplerate':int(vals.get('capture_rate') or 48000)}})
    except Exception:
        pass
    try:
        from audio_os_backend import list_input_devices
        for idx,name,meta in list_input_devices(force=True):
            keep={k:meta.get(k) for k in ('name','max_input_channels','max_output_channels','default_samplerate','hostapi') if k in meta}
            audio.append({'index':int(idx),'name':str(name),'meta':keep})
    except Exception:
        pass
    # R23n: query UCM through hw:<card> first.  On SOF-HDA, using the plain
    # card id (often ``sofhdadsp``) can miss the UCM profile entirely.  The UCM
    # CapturePCM is the authoritative internal-DMIC route when available.
    if shutil.which('arecord') and shutil.which('alsaucm'):
        try:
            cards=[]
            txt=Path('/proc/asound/cards').read_text(errors='ignore') if Path('/proc/asound/cards').is_file() else ''
            for line in txt.splitlines():
                m=re.match(r'^\s*(\d+)\s+\[([^]]+)\]',line)
                if m: cards.append((m.group(1),m.group(2).strip()))
            for card_i,card_id in cards:
                pcm=''
                for key in ('CapturePCM/Mic:sof-dsp/HiFi','CapturePCM/Mic/HiFi','CapturePCM/InternalMic/HiFi','CapturePCM/DigitalMic/HiFi'):
                    cp=subprocess.run(['alsaucm','-c',f'hw:{card_i}','get',key],capture_output=True,text=True,timeout=1.2,check=False)
                    if cp.returncode==0:
                        vals=[x.strip().strip('"\'') for x in (cp.stdout or '').splitlines() if x.strip()]
                        pcm=next((x for x in reversed(vals) if x.startswith(('hw:','plughw:','plug:'))),'')
                        if pcm: break
                if pcm:
                    dev=pcm if pcm.startswith('plug') else ('plughw:'+pcm[3:] if pcm.startswith('hw:') else pcm)
                    name=f'{card_id} · Internal Microphone (UCM)'
                    # sof-hda-dsp names its built-in DMIC `Mic:sof-dsp`; the
                    # matching UCM config may expose 1, 2 or 4 capture channels.
                    ch=2
                    try:
                        devname=key.split('/',2)[1]
                        cc=subprocess.run(['alsaucm','-c',f'hw:{card_i}','get',f'CaptureChannels/{devname}/HiFi'],capture_output=True,text=True,timeout=1.0,check=False)
                        nums=re.findall(r'\b([1-8])\b',cc.stdout or '')
                        if nums: ch=int(nums[-1])
                    except Exception: pass
                    audio.insert(0,{'index':-2000-len(audio),'name':name,'backend':'alsa','device':dev,
                                    'meta':{'backend':'alsa','alsa_device':dev,'ucm':True,'ucm_pcm':pcm,'card':card_i,'card_id':card_id,'max_input_channels':ch,'capture_channels':ch,'default_samplerate':48000}})
        except Exception:
            pass
    # R23l: minimal sOS may expose the physical internal microphone through
    # ALSA before PortAudio/PipeWire publishes it. Preserve that route instead
    # of returning an empty selector.
    if shutil.which('arecord'):
        try:
            cp=subprocess.run(['arecord','-l'],capture_output=True,text=True,timeout=2.0,check=False)
            rx=re.compile(r'^card\s+(\d+):\s*([^\s\[]+).*?device\s+(\d+):\s*(.*)$',re.I)
            seen={(str(x.get('name','')).casefold(), str((x.get('meta') or {}).get('alsa_device',''))) for x in audio}
            for line in (cp.stdout or '').splitlines():
                m=rx.search(line.strip())
                if not m: continue
                card_i,card_id,dev_i,desc=m.groups(); dev=f'plughw:CARD={card_id},DEV={dev_i}'
                name=f'{card_id} · {desc.strip() or "capture"}'
                key=(name.casefold(),dev)
                if key in seen: continue
                audio.append({'index':-1000-len(audio),'name':name,'backend':'alsa','device':dev,
                              'meta':{'backend':'alsa','alsa_device':dev,'card':card_i,'card_id':card_id,'device_index':dev_i,'max_input_channels':2,'default_samplerate':48000}})
                seen.add(key)
        except Exception:
            pass
    cameras=[]
    for node in sorted(glob.glob('/dev/video*')):
        try:
            namep=Path('/sys/class/video4linux')/Path(node).name/'name'
            name=namep.read_text(errors='ignore').strip() if namep.is_file() else Path(node).name
        except Exception:
            name=Path(node).name
        cameras.append({'path':node,'name':name or Path(node).name})
    media=[]; seen=set(); home=Path.home()
    candidates=[Path('/run/media')/home.name, Path('/run/media/groovebox'), Path('/media')/home.name, Path('/media')]
    try: candidates.append(Path(f'/run/user/{os.getuid()}/gvfs'))
    except Exception: pass
    for parent in candidates:
        try:
            if not parent.is_dir(): continue
            for child in sorted(parent.iterdir(), key=lambda p:p.name.lower()):
                if not child.is_dir(): continue
                rp=str(child.resolve())
                if rp in seen: continue
                seen.add(rp); media.append({'label':child.name,'path':rp})
        except Exception:
            pass
    return {'audio_inputs':audio,'cameras':cameras,'media_sources':media}

def _lane_timeout():
    try:
        return max(0.5,float(os.environ.get('GROOVEBOX_HW_LANE_TIMEOUT','4.0')))
    except Exception:
        return 4.0

def _emit_checkpoint(merged, errors):
    # GROOVEBOX_HW_PARTIAL_CHECKPOINT_20261030: emit after every completed lane.
    # The GUI keeps the last complete JSON line, so one stalled lane (hung
    # bluetoothctl/wpctl/PortAudio) can no longer blank the whole Hardware page.
    try:
        snap=dict(merged)
        if errors: snap['_errors']=list(errors)
        print(json.dumps(snap,separators=(',',':'),default=str),flush=True)
    except Exception:
        pass

def _hardware():
    from hardware_hub import scan_component
    merged={}; errors=[]; done=queue.Queue(); deadline=time.monotonic()+_lane_timeout()
    pending={'audio','video','display','input'}
    def _lane(kind):
        try: done.put((kind,scan_component(kind),None))
        except Exception as exc: done.put((kind,None,f'{kind}: {exc}'))
    # GROOVEBOX_HW_PARALLEL_LANES_20261031: all four families run concurrently.
    # Previously a single hung lane serialized the rest and held the helper open
    # until the outer subprocess timeout, leaving the Hardware page half blank.
    for kind in ('audio','display','input','video'):
        threading.Thread(target=_lane,args=(kind,),daemon=True,name='GrooveboxHWLane-'+kind).start()
    while pending:
        remain=deadline-time.monotonic()
        if remain<=0: break
        try: kind,part,err=done.get(timeout=remain)
        except queue.Empty:
            break
        if kind not in pending: continue
        pending.discard(kind)
        if err:
            errors.append(err)
        else:
            for k,v in (part or {}).items():
                if k=='tools' and isinstance(v,dict): merged.setdefault('tools',{}).update(v)
                elif v is not None: merged[k]=v
        _emit_checkpoint(merged, errors)
    for kind in ('audio','display','input','video'):
        if kind in pending:
            errors.append(f'{kind}: timed out after {_lane_timeout():.1f} s')
    if errors:
        merged['_errors']=list(errors)
        _emit_checkpoint(merged, errors)
    return merged

def main():
    _nice(); mode=(sys.argv[1] if len(sys.argv)>1 else 'record').lower()
    try:
        out=_hardware() if mode=='hardware' else _record()
        print(json.dumps(out,separators=(',',':'),default=str)); return 0
    except Exception as exc:
        print(str(exc),file=sys.stderr); return 2
if __name__=='__main__': raise SystemExit(main())
