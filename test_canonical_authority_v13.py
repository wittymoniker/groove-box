import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from canonical_authority import CanonicalAuthority

class Fake:
    def __init__(self):
        self.n=0
    def _legacy_project_snapshot(self):
        self.n += 1
        return {"seed":"42","bpm":120,"instrument_param_state":{"A":{"gain":.5}},"cross_media":{}}
    def _legacy_apply_project_snapshot(self, data):
        self.loaded=data

f=Fake(); a=CanonicalAuthority(f)
d=a.sync_from_live()
assert d["seed"] == "42"
a.write("instrument_param_state.A.gain", .75)
assert a.read("instrument_param_state.A.gain") == .75
payload=a.read(); a.apply_to_live(payload)
assert f.loaded["instrument_param_state"]["A"]["gain"] == .75
assert a.fingerprint
print("canonical authority v13: 3/3 passed")
