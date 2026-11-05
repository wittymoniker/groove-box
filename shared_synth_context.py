"""Versioned, deterministic shared event context for peer-level synth lanes.

All lanes have equal scheduling priority. Events are ordered by time then stable
lane/event identifiers; lane names never imply precedence or gain dominance.
"""
from __future__ import annotations
import copy, hashlib, json, math
from spatial_synth_engines import throw_ball, cellular_automaton

CONTEXT_VERSION = 2
# Fixed bus allocation requested for the shared spatial/canonical synth group.
# The remaining instruments occupy the complementary bus. These are linear
# amplitude gains; the near-unity sum is preserved exactly as specified.
SPATIAL_SYNTH_BUS_GAIN = 0.19758
OTHER_INSTRUMENT_BUS_GAIN = 0.8024
SPATIAL_LANES = ("vector", "bouncing_ball", "wavetable", "cellular_automata")
PKP_DJ_BOOST_DEFAULT = 0.5
# Carrier generators are single-instance global sources, at half the global sidechain depth.
GLOBAL_CARRIER_LANES = ("vector", "bouncing_ball", "wavetable", "cellular_automata")
GLOBAL_CARRIER_SIDECHAIN_RATIO = 0.5
GOAVA_CANONICAL_AMPLITUDE = 0.19758
GOAVA_CANONICAL_AMPLITUDE = 0.19758

def apply_bus_allocation(context):
    """Attach explicit bus allocation metadata and per-event gain to a context.

    Scheduling remains peer-concurrent: bus gain does not change event order or
    lane priority. The four spatial/canonical lanes share one bus budget.
    """
    ctx = copy.deepcopy(context)
    ctx["mix_policy"] = {
        "version": 1,
        "spatial_lanes": list(SPATIAL_LANES),
        "spatial_bus_gain": SPATIAL_SYNTH_BUS_GAIN,
        "other_instruments_bus_gain": OTHER_INSTRUMENT_BUS_GAIN,
        "pkp_dj_boost_default": PKP_DJ_BOOST_DEFAULT,
        "pkp_dj_boost_source_gain": 1.0,
        "pkp_dj_boost_wet_mix": PKP_DJ_BOOST_DEFAULT,
        "priority_policy": "equipotent-peer-lanes",
        "global_carrier_policy": "single-instance-global-carrier-wave-generators",
        "global_carrier_sidechain_ratio": GLOBAL_CARRIER_SIDECHAIN_RATIO,
        "goava_canonical_amplitude": GOAVA_CANONICAL_AMPLITUDE,
    }
    for lane_name, lane in ctx.get("lanes", {}).items():
        lane["bus"] = "spatial_canonical" if lane_name in SPATIAL_LANES else "other_instruments"
        lane["bus_gain"] = SPATIAL_SYNTH_BUS_GAIN if lane_name in SPATIAL_LANES else OTHER_INSTRUMENT_BUS_GAIN
        lane["instance_scope"] = "global-singleton" if lane_name in GLOBAL_CARRIER_LANES else lane.get("instance_scope", "lane")
        lane["sidechain_depth_scale"] = GLOBAL_CARRIER_SIDECHAIN_RATIO if lane_name in GLOBAL_CARRIER_LANES else 1.0
    for event in ctx.get("schedule", []):
        event["bus_gain"] = SPATIAL_SYNTH_BUS_GAIN if event.get("lane") in SPATIAL_LANES else OTHER_INSTRUMENT_BUS_GAIN
        event["instance_scope"] = "global-singleton" if event.get("lane") in GLOBAL_CARRIER_LANES else "event"
        event["sidechain_depth_scale"] = GLOBAL_CARRIER_SIDECHAIN_RATIO if event.get("lane") in GLOBAL_CARRIER_LANES else 1.0
    payload=json.dumps({k:v for k,v in ctx.items() if k!="fingerprint"},sort_keys=True,separators=(",",":"),default=str).encode()
    ctx["fingerprint"] = hashlib.sha256(payload).hexdigest()
    return ctx

PEER_LANES = ("vector", "wavetable", "bouncing_ball", "cellular_automata", "user_synth", "math_pattern")

def empty_context():
    return {"format":"groovebox-shared-synth-context", "version":CONTEXT_VERSION,
            "revision":0, "lanes":{name:{"enabled":False,"events":[],"parameters":{}} for name in PEER_LANES},
            "schedule":[], "heuristics":{}, "algorithms":{}, "ownership":"canonical-shared-peer-lanes", "activity_locks":{}}

def _stable_id(lane, index, event):
    raw=json.dumps([lane,index,event],sort_keys=True,separators=(",",":"),default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:16]

def apply_base_frequency(context, base_frequency=432.0):
    """Write the global base-frequency tuning into every geometric carrier.

    Canonical-owned frequency fields are regenerated deterministically. Fields
    explicitly marked user_data_protected are preserved byte-for-byte; user
    program data and geometry are never overwritten by this tuning pass.
    MIDI pitch 69 is the reference pitch for the supplied base frequency.
    """
    ctx=copy.deepcopy(context)
    old_base=float(ctx.get("base_frequency_hz",base_frequency) or base_frequency)
    base=max(0.0,min(50000.0,float(base_frequency)))
    ctx["base_frequency_hz"]=base
    ctx.setdefault("canonical_predictions", {})["global_carrier_frequency"]={
        "base_frequency_hz":base,"reference_pitch":69,
        "policy":"base-frequency-spinner; canonical-owned-fields-only"}
    # The four geometric carriers are global singletons. Musical synth, video,
    # and game patterns also participate when their events explicitly carry a
    # MIDI pitch (or opt in with frequency_derived=True). Purely visual/game
    # fields are left alone; only frequency-bearing events are retuned.
    for lane_name, lane in ctx.get("lanes", {}).items():
        if not isinstance(lane,dict):
            continue
        params=lane.setdefault("parameters", {})
        # Every peer lane sees the shared anchor. The four geometric carriers
        # additionally advertise single-instance scope via apply_bus_allocation.
        if not params.get("user_data_protected", False):
            params["canonical_base_frequency_hz"]=base
            params["canonical_frequency_source"]="spin_base_frequency"
        for event in lane.get("events", []):
            if not isinstance(event,dict) or event.get("user_data_protected", False):
                continue
            if event.get("frequency_user_owned", False):
                continue
            try:
                if "frequency_ratio" in event:
                    ratio=float(event.get("frequency_ratio",1.0))
                    frequency=base*ratio
                elif "pitch" in event:
                    pitch=float(event.get("pitch",69))
                    frequency=base*(2.0**((pitch-69.0)/12.0))
                elif event.get("frequency_derived", False):
                    previous=float(event.get("frequency_hz",old_base))
                    ratio=previous/old_base
                    frequency=base*ratio
                else:
                    continue
                if not math.isfinite(frequency) or frequency<0.0:
                    continue
            except (TypeError,ValueError,OverflowError):
                continue
            event["frequency_hz"]=frequency
            event["frequency_source"]="canonical-base-frequency"
            event["base_frequency_hz"]=base
    return ctx

def rebuild_schedule(context):
    """Rebuild deterministic concurrent schedule without lane-priority semantics."""
    ctx=copy.deepcopy(context)
    events=[]
    for lane_name,lane in sorted(ctx.get("lanes",{}).items()):
        if not isinstance(lane,dict) or not lane.get("enabled",False): continue
        for i,ev in enumerate(lane.get("events",[])):
            if not isinstance(ev,dict): continue
            item=dict(ev); item["lane"]=lane_name; item["event_id"]=_stable_id(lane_name,i,ev)
            item["time"] = max(0.0,float(item.get("time",item.get("step",0))))
            item["velocity"] = max(0,min(127,int(item.get("velocity",100))))
            events.append(item)
    # Stable sort only establishes reproducible serialization; equal-time events remain concurrent.
    events.sort(key=lambda e:(e["time"],e["lane"],e["event_id"]))
    ctx["schedule"]=events
    ctx=apply_bus_allocation(ctx)
    payload=json.dumps({k:v for k,v in ctx.items() if k!="fingerprint"},sort_keys=True,separators=(",",":"),default=str).encode()
    ctx["fingerprint"]=hashlib.sha256(payload).hexdigest()
    return ctx

def set_lane(context, lane_name, events, parameters=None, enabled=True):
    ctx=copy.deepcopy(context or empty_context())
    ctx.setdefault("lanes",{})[str(lane_name)]={"enabled":bool(enabled),"events":[dict(e) for e in events],"parameters":dict(parameters or {})}
    ctx["revision"]=int(ctx.get("revision",0))+1
    return rebuild_schedule(ctx)

def generate_spatial_lanes(context, ball_parameters=None, ca_parameters=None, base_frequency_hz=None):
    ctx=copy.deepcopy(context or empty_context())
    bp=dict(ball_parameters or {})
    ball=throw_ball(steps=bp.get("steps",64),x=bp.get("x",0),y=bp.get("y",0),vx=bp.get("vx",.7),vy=bp.get("vy",-.4),gravity_coefficients=bp.get("gravity_coefficients",[0,0,.25]),radius=bp.get("radius",1),dt=bp.get("dt",.025),gravity_angle_degrees=bp.get("gravity_angle_degrees",90.0),reverse_polarity_on_hit=bp.get("reverse_polarity_on_hit",True),initial_polarity=bp.get("initial_polarity",1))
    ball_events=[]
    for s in ball["samples"]:
        # Every boundary collision is a sound event; event time is simulation step.
        if s["collision"] or s["step"] % 4 == 0:
            ball_events.append({"time":s["step"],"pitch":36+int(round((s["x"]+1)*23.5)),"velocity":max(1,min(127,int(45+s["speed"]*20))),"x":s["x"],"y":s["y"],"collision":s["collision"]})
    if canonical_may_start(ctx, "bouncing_ball"):
        ctx=set_lane(ctx,"bouncing_ball",ball_events,{"engine":ball,"parameters":bp},True)
    cp=dict(ca_parameters or {})
    ca=cellular_automaton(width=cp.get("width",16),height=cp.get("height",16),cell_types=cp.get("cell_types",3),initial=cp.get("initial"),rules=cp.get("rules",[]),generations=cp.get("generations",16),neighborhood=cp.get("neighborhood","moore"))
    ca_events=[]
    for e in ca["events"]:
        ca_events.append({"time":e["y"]*ca["width"]+e["x"],"pitch":e["pitch"],"velocity":e["velocity"],"cell_x":e["x"],"cell_y":e["y"],"state":e["state"]})
    if canonical_may_start(ctx, "cellular_automata"):
        ctx=set_lane(ctx,"cellular_automata",ca_events,{"engine":ca,"parameters":cp},True)
    ctx["heuristics"]={**ctx.get("heuristics",{}),"shared_density":len(ctx["schedule"]),"overlap_policy":"peer-concurrent-no-dominant-lane"}
    ctx["algorithms"]={**ctx.get("algorithms",{}),"event_order":"time+stable-id","deterministic":True}
    active_base=ctx.get("base_frequency_hz",432.0) if base_frequency_hz is None else base_frequency_hz
    return rebuild_schedule(apply_base_frequency(ctx, active_base))

def set_activity_lock(context, lane_name, active, reason="user-activity"):
    """Lock canonical auto-start for a lane after direct user activity.

    The lock is intentionally released only by explicit reset or a declared
    no-activity reset; canonical updates may still shape the lane parameters.
    """
    ctx=copy.deepcopy(context or empty_context())
    locks=ctx.setdefault("activity_locks", {})
    lane_name=str(lane_name)
    if active:
        locks[lane_name]={"locked":True,"reason":str(reason),"user_owned":True}
    else:
        locks.pop(lane_name, None)
    ctx["revision"]=int(ctx.get("revision",0))+1
    return rebuild_schedule(ctx)

def reset_activity_lock(context, lane_name):
    return set_activity_lock(context, lane_name, False, "explicit-reset")

def canonical_may_start(context, lane_name):
    lock=(context or {}).get("activity_locks", {}).get(str(lane_name), {})
    return not bool(lock.get("locked", False))


def validate_context(context):
    assert context.get("format")=="groovebox-shared-synth-context"
    assert isinstance(context.get("lanes"),dict) and isinstance(context.get("schedule"),list)
    ids=[e.get("event_id") for e in context["schedule"]]
    assert len(ids)==len(set(ids)),"event IDs must be unique"
    assert all(e.get("lane") in context["lanes"] for e in context["schedule"])
    return True

def publish_program_lanes(context, vector_state=None, wavetable_state=None, user_synth_events=None, math_pattern_events=None):
    """Publish current Vector/Wavetable program states into the shared canonical event space.

    This is a deterministic bridge representation; audio renderers may consume the same
    lane records without making one instrument the transport owner.
    """
    ctx=copy.deepcopy(context or empty_context())
    vs=dict(vector_state or {}); ws=dict(wavetable_state or {})
    vx,vy,vz=(float(vs.get(k,0.0)) for k in ("x","y","z"))
    drive=max(0.0,min(1.0,float(vs.get("drive",.5))))
    vector_events=[]
    for i,v in enumerate((vx,vy,vz)):
        vector_events.append({"time":i*4,"pitch":max(0,min(127,48+int(round(v*24)))),"velocity":max(1,min(127,int(48+drive*79))),"axis":"xyz"[i],"value":v})
    if canonical_may_start(ctx, "vector"):
        ctx=set_lane(ctx,"vector",vector_events,{"program_state":vs,"canonical_source":True},bool(vs.get("enabled",True)))
    phase=float(ws.get("phase",0.0)); curvature=float(ws.get("curvature",.5)); twist=float(ws.get("twist",.5)); fold=float(ws.get("fold",.2))
    wavetable_events=[]
    for i in range(8):
        value=(phase+i/8.0+curvature*.25+twist*.125+fold*.0625)%1.0
        wavetable_events.append({"time":i*2,"pitch":36+int(round(value*48)),"velocity":max(1,min(127,int(48+float(ws.get("canonical_share",.5))*79))),"phase":value,"partial":i})
    if canonical_may_start(ctx, "wavetable"):
        ctx=set_lane(ctx,"wavetable",wavetable_events,{"program_state":ws,"canonical_source":True},True)
    if user_synth_events is not None: ctx=set_lane(ctx,"user_synth",user_synth_events,{"source":"user_synth_library"},True)
    if math_pattern_events is not None: ctx=set_lane(ctx,"math_pattern",math_pattern_events,{"source":"mathematical_composition_lab"},True)
    ctx["canonical_inputs"]={"vector":vs,"wavetable":ws}
    return rebuild_schedule(apply_base_frequency(ctx, ctx.get("base_frequency_hz", 432.0)))
