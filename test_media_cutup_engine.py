import math, os, tempfile, wave
import numpy as np
from media_cutup_engine import estimate_pitch_hz, generate_cut_events, playlist_geometric_parameters, render_cutup

def make_sine(path, hz=220.0, sr=48000, seconds=2.0):
    t=np.arange(int(sr*seconds))/sr
    x=(0.35*np.sin(2*math.pi*hz*t)*32767).astype('<i2')
    with wave.open(path,'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(x.tobytes())

def main():
    with tempfile.TemporaryDirectory() as td:
        src=os.path.join(td,'a.wav'); out=os.path.join(td,'cut.wav')
        make_sine(src)
        hz=estimate_pitch_hz(src)
        assert hz and abs(hz-220.0)<3.0, hz
        e1=generate_cut_events(2.0,bpm=120,bars=1,steps_per_bar=8,seed=123,slice_divisions=8)
        e2=generate_cut_events(2.0,bpm=120,bars=1,steps_per_bar=8,seed=123,slice_divisions=8)
        assert e1==e2 and len(e1)==8
        p1=playlist_geometric_parameters(10,123)
        p2=playlist_geometric_parameters(10,123)
        assert p1==p2
        render_cutup(src,out,e1,120,8)
        assert os.path.isfile(out) and os.path.getsize(out)>1000
        assert os.path.isfile(out+'.cutup.json')
        print('media cutup engine OK', hz, os.path.getsize(out))
if __name__=='__main__': main()
