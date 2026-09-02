from videogame_engine import SequenceInfluence, ScenographLite, MusicBed

seed = 42
s1 = SequenceInfluence(seed, (8, 13, 21))
s2 = SequenceInfluence(seed, (8, 13, 21))
a = s1.update(5.25)
b = s2.update(5.25)
assert a == b, "sequence controller must be deterministic"
assert 0.0 < a['motion'] <= 1.0, a
assert 0.0 < a['vibration'] <= 0.5, a
assert a['step'] == 5

scene = ScenographLite(seed, n=8)
scene.sequence_control = SequenceInfluence(seed, (8, 13, 21))
scene.tick(0.01)
y0 = [x['yaw'] for x in scene.layers]
scene.tick(0.01)
y1 = [x['yaw'] for x in scene.layers]
assert any(abs(a-b) > 1e-12 for a,b in zip(y0,y1)), "sequence should drive object motion"

m = MusicBed(seed, bars=8)
m.sequence_control.pattern_lengths = (8, 13, 21)
m.step(0.05)
assert 0.0 < m.sequence_vibration <= 0.5
print('PASS: deterministic sequence conductor')
print('PASS: sequence drives visual object movement')
print('PASS: sound vibration is bounded to 0.5 factor')
