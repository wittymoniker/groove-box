import unittest
from videogame_engine import PlanetaryWorld, SpriteGrammar, _vlen, _vdot

class PlanetaryTests(unittest.TestCase):
    def test_deterministic_system(self):
        a=PlanetaryWorld(77); b=PlanetaryWorld(77)
        self.assertEqual(a.planets,b.planets); self.assertEqual(a.pos,b.pos)
    def test_gravity_and_tangent_camera(self):
        w=PlanetaryWorld(77)
        w.step(1/30,(0,0,1))
        r,u,f=w.local_frame()
        self.assertAlmostEqual(_vdot(f,w.gravity),0.0,places=6)
        self.assertAlmostEqual(_vdot(r,w.gravity),0.0,places=6)
    def test_sprite_composition_is_finite_vocabulary(self):
        g=SpriteGrammar(9)
        e=g.encounter(1000000)
        self.assertTrue(set(e['parts']).issubset(set(g.PARTS)))

if __name__=='__main__': unittest.main()
