import numpy as np
import canonical_cross_media as cm

def test_wave_deterministic():
    x=np.sin(np.linspace(0,100,48000,dtype=np.float64))*0.25
    a=cm.analyze_waveform(x,48000)
    b=cm.analyze_waveform(x,48000)
    assert a==b
    assert a['available'] and a['samples']==48000

def test_document_and_projection():
    class W:
        def __init__(self,v): self.v=v
        def value(self): return self.v
    class App:
        spin_bpm=W(120); spin_seq_length=W(16); spin_playlist_length=W(32); spin_base_frequency=W(432); spin_global_convolve=W(0)
        imported_wav_path='a.wav'; imported_video_path='v.mp4'; media_video_mix=.5
        instrument_sequencer_memory={'A':{'steps':[1,0], 'gates':[True,False]}}
        instrument_sequence_banks={}; instrument_selected_sequence={'A':0}; master_playlist_data=[]; playlist_automation=[]
        instrument_scripts={}; instrument_param_state={}; instrument_sample_paths={}; patch_connections=[]; global_algo_state={}; operator_time_offsets={}
        def _seed_text(self): return '123'
        class D:
            def to_json(self): return {}
        domain_eq_engine=D()
    d=cm.build_canonical_document(App(), np.zeros(1000), 1000)
    assert d['cross_media_fingerprint']
    p=cm.frame_projection(d, .25)
    assert 'energy' in p and p['composition_fingerprint']==d['composition_fingerprint']

if __name__=='__main__':
    test_wave_deterministic(); test_document_and_projection(); print('cross-media tests: 2/2 passed')
