from pathlib import Path
r=Path(__file__).resolve().parent
checks={}
a=(r/'audio_os_backend.py').read_text(errors='replace')
l=(r/'layered_signal_lab.py').read_text(errors='replace')
h=(r/'hardware_hub.py').read_text(errors='replace')
p=(r/'performance.py').read_text(errors='replace')
g=(r/'groovebox.py').read_text(errors='replace')
w=(r/'web_browser_tab.py').read_text(errors='replace')
m=(r/'media_output_router.py').read_text(errors='replace')
rem=(r/'BUILD_ISO/v35_22zz/sos-removable-media-v35_22zz_r7').read_text(errors='replace')
checks['cached audio resolver']='GROOVEBOX_V35_22ZZ_R14_AUDIO_ROUTE_CACHE_20260930' in a and 'resolve_output_device_index' in a and 'play_buffer' in a
checks['sample preview routed']='play_buffer(self._preview' in l
checks['main streams routed']='open_output_stream(' in g and "_preferred_audio_output_name" in g
checks['true component scans']='GROOVEBOX_V35_22ZZ_R14_TRUE_COMPONENT_SCANS_20260930' in h and "'audio':_scan_audio_only" in h
checks['no full scan per component']='r=scan(); k=' not in h
checks['browser status deferred']='Network status is deferred' in w
checks['webengine relaunch excluded']='R14: Chromium/QtWebEngine' in g
checks['video audio-fallback']=('R14_MEDIA_PLAYBACK_RESILIENCE' in m and
    ('--audio-fallback-to-null=yes' in m or
     ('GROOVEBOX_V35_22ZZ_R23_PLAYBACK_OUTPUT_RECOVERY_20261001' in m
      and '--audio-fallback-to-null=no' in m
      and '--audio-samplerate=48000' in m
      and '_preferred_alsa_output_device' in m
      and 'args.append("--ao=null")' not in m)))
checks['reader diagnostic']='microSD reader' in p and 'Rescan Reader' in p
checks['deep reader rescan']='GROOVEBOX_V35_22ZZ_R14_MICROSD_DEEP_RESCAN_20260930' in rem and '/sys/bus/pci/rescan' in rem and '/sys/class/scsi_host/host' in rem
for name,ok in checks.items(): print(('PASS: ' if ok else 'FAIL: ')+name)
if not all(checks.values()): raise SystemExit(1)
print('PASS: v35.22zz-R14 audio/video/performance/microSD latency contracts')
