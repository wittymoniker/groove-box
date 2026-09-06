import os,tempfile
from mcc_integrity import write_sidecar,verify,select_verified
def test_integrity_and_recovery():
    with tempfile.TemporaryDirectory() as d:
        p=os.path.join(d,"x.MCC"); prev=p+".prev"
        open(prev,"wb").write(b'{"good":1}'); write_sidecar(prev)
        open(p,"wb").write(b'{"good":2}'); write_sidecar(p)
        assert verify(p)[0]
        open(p,"ab").write(b"corrupt"); assert not verify(p)[0]
        assert select_verified(p)==(prev,"recovered-prev")
