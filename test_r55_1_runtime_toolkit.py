import unittest
from groovebox_runtime import (CircuitBreaker,CircuitOpen,HealthLedger,MIDIAdapter,
 BluetoothAdapter,RadioCATAdapter,AdapterUnavailable,OperationLog,get_profile)

class Backend:
 def __init__(self): self.sent=[]; self.ptt=[]; self.closed=False
 def send(self,x): self.sent.append(x); return True
 def close(self): self.closed=True
 def query(self,x): return 'OK'
 def set_ptt(self,x): self.ptt.append(x); return x
 def discover(self,t): return ['device']

class ToolkitTests(unittest.TestCase):
 def test_circuit_breaker(self):
  b=CircuitBreaker(2,0.01); b.failure(); b.failure()
  with self.assertRaises(CircuitOpen): b.before_call()
  import time; time.sleep(.02); b.before_call(); b.success(); self.assertEqual(b.state,'closed')
 def test_health_bounded(self):
  h=HealthLedger(2); h.record('ui','info','a'); h.record('ui','warning','b'); h.record('ui','error','c'); self.assertEqual(len(h.snapshot()),2)
 def test_midi_injection(self):
  with self.assertRaises(AdapterUnavailable): MIDIAdapter().send(b'\x90\x40\x7f')
  backend=Backend(); m=MIDIAdapter(backend); self.assertTrue(m.send(b'\x90\x40\x7f')); m.close(); self.assertTrue(backend.closed)
 def test_bluetooth_injection(self): self.assertEqual(BluetoothAdapter(Backend()).discover(),('device',))
 def test_radio_ptt_guard(self):
  b=Backend(); r=RadioCATAdapter(b)
  with self.assertRaises(PermissionError): r.set_ptt(True,operator_confirmed=True)
  r=RadioCATAdapter(b,allow_transmit=True); r.set_ptt(True,operator_confirmed=True); r.close(); self.assertEqual(b.ptt,[True,False])
 def test_collaboration_merge(self):
  a=OperationLog('a'); b=OperationLog('b'); a.apply(('track','name'),'one'); b.merge(a.export()); b.apply(('track','name'),'two'); a.merge(b.export()); self.assertEqual(a.materialize()[('track','name')],'two'); self.assertIn(('track','name'),a.conflicts())
 def test_profile_copy(self):
  p=get_profile('dell_latitude_3510'); p['notes'].append('mutated'); self.assertNotIn('mutated',get_profile('dell_latitude_3510')['notes'])
if __name__=='__main__': unittest.main()
