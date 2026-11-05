import unittest
import numpy as np
from concurrent_audio_bus import ConcurrentAudioBus

class ConcurrentAudioBusTests(unittest.TestCase):
    def test_two_sources_sum_concurrently(self):
        bus=ConcurrentAudioBus()
        bus.publish('transport',np.array([.1,.2,.3],dtype=np.float32))
        bus.publish('synth',np.array([.4,.3,.2],dtype=np.float32))
        out=np.zeros(3,dtype=np.float32); bus.mix_into(out)
        np.testing.assert_allclose(out,[.5,.5,.5],rtol=1e-6,atol=1e-6)

    def test_remove_source_does_not_remove_other_source(self):
        bus=ConcurrentAudioBus(); bus.publish('a',[.25,.25]); bus.publish('b',[.5,.5]); bus.remove('a')
        out=np.zeros(2,dtype=np.float32); bus.mix_into(out); np.testing.assert_allclose(out,[.5,.5])

    def test_loop_and_gain(self):
        bus=ConcurrentAudioBus(); bus.publish('loop',[.5],gain=.5,loop=True)
        out=np.zeros(4,dtype=np.float32); bus.mix_into(out); np.testing.assert_allclose(out,[.25]*4)

    def test_zero_master_gain_is_left_to_single_downstream_gain(self):
        bus=ConcurrentAudioBus(); bus.publish('a',[.5,.5]); out=np.zeros(2,dtype=np.float32); bus.mix_into(out)
        master=0.0; out *= master; np.testing.assert_array_equal(out,[0.,0.])

if __name__=='__main__': unittest.main()
