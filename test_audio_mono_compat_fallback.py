import numpy as np
from audio_os_backend import _mono_compat_callback

def test_stereo_to_mono_fold_down():
    def render(out, frames, time_info, status):
        out[:, 0] = 0.8
        out[:, 1] = -0.2
    cb = _mono_compat_callback(render, 2)
    out = np.zeros((16, 1), dtype=np.float32)
    cb(out, 16, None, None)
    assert np.allclose(out[:, 0], 0.3)

def test_multichannel_fold_down():
    def render(out, frames, time_info, status):
        out[:] = np.array([1.0, 0.0, -1.0, 0.0], dtype=np.float32)
    cb = _mono_compat_callback(render, 4)
    out = np.zeros((8, 1), dtype=np.float32)
    cb(out, 8, None, None)
    assert np.allclose(out[:, 0], 0.0)

if __name__ == '__main__':
    test_stereo_to_mono_fold_down(); test_multichannel_fold_down()
    print('PASS: mono compatibility fold-down')
