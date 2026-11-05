import unittest
from shared_synth_context import empty_context,set_lane,generate_spatial_lanes,validate_context

class SharedSynthContextTests(unittest.TestCase):
    def test_peer_lanes_overlap_without_priority(self):
        c=empty_context()
        c=set_lane(c,'vector',[{'time':2,'pitch':60,'velocity':90}],enabled=True)
        c=set_lane(c,'wavetable',[{'time':2,'pitch':64,'velocity':90}],enabled=True)
        same=[e for e in c['schedule'] if e['time']==2]
        self.assertEqual({e['lane'] for e in same},{'vector','wavetable'})
        self.assertEqual(len(same),2)
        self.assertTrue(validate_context(c))
    def test_spatial_generation_is_deterministic(self):
        a=generate_spatial_lanes(empty_context(),{'steps':32},{'width':8,'height':8,'cell_types':3,'generations':4})
        b=generate_spatial_lanes(empty_context(),{'steps':32},{'width':8,'height':8,'cell_types':3,'generations':4})
        self.assertEqual(a['fingerprint'],b['fingerprint'])
        self.assertIn('bouncing_ball',a['lanes']); self.assertIn('cellular_automata',a['lanes'])
    def test_external_synth_lanes_can_publish(self):
        c=empty_context()
        for lane in ('vector','wavetable','user_synth','math_pattern'):
            c=set_lane(c,lane,[{'time':0,'pitch':48,'velocity':100}],enabled=True)
        self.assertEqual(len(c['schedule']),4)
        self.assertEqual(len({e['lane'] for e in c['schedule']}),4)

if __name__=='__main__': unittest.main()

class MixPolicyTests(unittest.TestCase):
    def test_spatial_group_and_other_instrument_bus_gains(self):
        from shared_synth_context import (SPATIAL_SYNTH_BUS_GAIN,
            OTHER_INSTRUMENT_BUS_GAIN, set_lane, empty_context)
        ctx = set_lane(empty_context(), "vector", [{"time": 0, "pitch": 60}], enabled=True)
        ctx = set_lane(ctx, "user_synth", [{"time": 0, "pitch": 64}], enabled=True)
        by_lane = {e["lane"]: e for e in ctx["schedule"]}
        self.assertAlmostEqual(by_lane["vector"]["bus_gain"], SPATIAL_SYNTH_BUS_GAIN)
        self.assertAlmostEqual(by_lane["user_synth"]["bus_gain"], OTHER_INSTRUMENT_BUS_GAIN)
        self.assertAlmostEqual(SPATIAL_SYNTH_BUS_GAIN, 0.19758)
        self.assertAlmostEqual(OTHER_INSTRUMENT_BUS_GAIN, 0.8024)

    def test_spatial_lane_mix_does_not_change_peer_order_or_priority(self):
        from shared_synth_context import empty_context, set_lane
        ctx = empty_context()
        for lane in ("vector", "wavetable", "bouncing_ball", "cellular_automata"):
            ctx = set_lane(ctx, lane, [{"time": 1, "pitch": 60}], enabled=True)
        events = ctx["schedule"]
        self.assertEqual(len(events), 4)
        self.assertTrue(all(e["bus_gain"] == 0.19758 for e in events))
        self.assertEqual(len({e["time"] for e in events}), 1)

class GlobalCarrierPolicyTests(unittest.TestCase):
    def test_carriers_are_global_singletons_with_half_sidechain(self):
        from shared_synth_context import empty_context, set_lane, GLOBAL_CARRIER_LANES, GLOBAL_CARRIER_SIDECHAIN_RATIO
        ctx=empty_context()
        for lane in GLOBAL_CARRIER_LANES:
            ctx=set_lane(ctx,lane,[{"time":0,"pitch":60}],{},True)
            self.assertEqual(ctx["lanes"][lane]["instance_scope"], "global-singleton")
            self.assertEqual(ctx["lanes"][lane]["sidechain_depth_scale"], GLOBAL_CARRIER_SIDECHAIN_RATIO)
        self.assertEqual(GLOBAL_CARRIER_SIDECHAIN_RATIO, .5)
    def test_user_activity_lock_blocks_canonical_autostart_until_reset(self):
        from shared_synth_context import empty_context, set_activity_lock, canonical_may_start, reset_activity_lock
        ctx=set_activity_lock(empty_context(),"bouncing_ball",True,"user-bounce")
        self.assertFalse(canonical_may_start(ctx,"bouncing_ball"))
        self.assertTrue(canonical_may_start(reset_activity_lock(ctx,"bouncing_ball"),"bouncing_ball"))
    def test_cell_lock_is_independent_and_resettable(self):
        from shared_synth_context import empty_context, set_activity_lock, canonical_may_start, reset_activity_lock
        ctx=set_activity_lock(empty_context(),"cellular_automata",True,"single-cell-user-lock")
        self.assertFalse(canonical_may_start(ctx,"cellular_automata"))
        self.assertTrue(canonical_may_start(reset_activity_lock(ctx,"cellular_automata"),"cellular_automata"))

    def test_global_carriers_follow_base_frequency_and_preserve_protected_data(self):
        from shared_synth_context import empty_context, set_lane, apply_base_frequency
        ctx=empty_context()
        ctx=set_lane(ctx,"vector",[{"time":0,"pitch":69},{"time":1,"pitch":81,"user_data_protected":True,"frequency_hz":123.0}],{"user_data_protected":False},True)
        tuned=apply_base_frequency(ctx, 220.0)
        events=tuned["lanes"]["vector"]["events"]
        self.assertAlmostEqual(events[0]["frequency_hz"],220.0)
        self.assertEqual(events[1]["frequency_hz"],123.0)
        self.assertEqual(tuned["lanes"]["vector"]["parameters"]["canonical_base_frequency_hz"],220.0)
        self.assertEqual(tuned["base_frequency_hz"],220.0)


class BaseFrequencyPropagationTests(unittest.TestCase):
    def test_frequency_spinner_policy_covers_synth_video_game_and_carriers(self):
        from shared_synth_context import empty_context, set_lane, apply_base_frequency
        ctx=empty_context()
        for lane in ('vector','wavetable','bouncing_ball','cellular_automata','user_synth','math_pattern','video_pattern','game_pattern'):
            ctx=set_lane(ctx,lane,[{'time':0,'pitch':69}],enabled=True)
        ctx=set_lane(ctx,'video_pattern',[{'time':0,'pitch':69,'user_data_protected':True,'frequency_hz':777.0}],enabled=True)
        tuned=apply_base_frequency(ctx, 220.0)
        for lane in ('vector','wavetable','bouncing_ball','cellular_automata','user_synth','math_pattern','game_pattern'):
            self.assertAlmostEqual(tuned['lanes'][lane]['events'][0]['frequency_hz'],220.0,lane)
        self.assertEqual(tuned['lanes']['video_pattern']['events'][0]['frequency_hz'],777.0)
        self.assertEqual(tuned['lanes']['video_pattern']['events'][0].get('frequency_source'),None)

    def test_non_musical_visual_event_is_not_rewritten(self):
        from shared_synth_context import empty_context, set_lane, apply_base_frequency
        ctx=set_lane(empty_context(),'video_pattern',[{'time':0,'x':10,'y':20,'hue':0.4}],enabled=True)
        tuned=apply_base_frequency(ctx,330.0)
        self.assertNotIn('frequency_hz',tuned['lanes']['video_pattern']['events'][0])


def test_base_frequency_retarget_uses_previous_base_for_derived_ratio():
    from shared_synth_context import empty_context, apply_base_frequency
    ctx=empty_context()
    ctx['base_frequency_hz']=100.0
    ctx['lanes']['vector']['enabled']=True
    ctx['lanes']['vector']['events']=[{'frequency_derived':True,'frequency_hz':200.0}]
    result=apply_base_frequency(ctx,200.0)
    assert result['lanes']['vector']['events'][0]['frequency_hz']==400.0
    assert result['lanes']['vector']['events'][0]['base_frequency_hz']==200.0
