"""Seeded, reproducible media-graph construction with validation and provenance."""
from __future__ import annotations
import hashlib, json, math, platform, time
from copy import deepcopy
from .catalog import RECIPES, get_recipe

SCHEMA_VERSION = "1.0"
MAX_SEED_CHARS = 512
MAX_NODES = 4096
ALLOWED_KINDS = {"seed", "audio", "video", "game", "math", "camera", "edit", "export", "parameter"}
class FoundryError(ValueError): pass

def _digest(*parts):
    h=hashlib.blake2b(digest_size=32, person=b"MGR-foundry-v1")
    for part in parts:
        b=str(part).encode("utf-8", "strict"); h.update(len(b).to_bytes(4,"little")); h.update(b)
    return h.hexdigest()

def _unit(seed, recipe_id, key):
    return int(_digest(seed, recipe_id, key)[:16],16) / float(0xffffffffffffffff)

def _finite(value, label):
    try: x=float(value)
    except (TypeError,ValueError): raise FoundryError(f"{label} must be numeric") from None
    if not math.isfinite(x): raise FoundryError(f"{label} must be finite")
    return x

def validate_project(project):
    """Validate graph shape, finite controls, unique IDs and acyclic dependencies."""
    if not isinstance(project,dict): raise FoundryError("project must be an object")
    if project.get("schema") != SCHEMA_VERSION: raise FoundryError("unsupported project schema")
    seed=project.get("seed")
    if not isinstance(seed,str) or not seed or len(seed)>MAX_SEED_CHARS: raise FoundryError("seed must be 1..512 characters")
    nodes=project.get("nodes")
    if not isinstance(nodes,list) or len(nodes)>MAX_NODES: raise FoundryError("nodes must be a bounded list")
    ids=set(); graph={}
    for node in nodes:
        if not isinstance(node,dict): raise FoundryError("each node must be an object")
        nid=node.get("id")
        if not isinstance(nid,str) or not nid or nid in ids: raise FoundryError("node IDs must be unique non-empty strings")
        ids.add(nid)
        if node.get("kind") not in ALLOWED_KINDS: raise FoundryError(f"unsupported node kind on {nid}")
        deps=node.get("depends_on",[])
        if not isinstance(deps,list) or any(not isinstance(x,str) for x in deps): raise FoundryError(f"invalid dependencies on {nid}")
        graph[nid]=deps
        params=node.get("params",{})
        if not isinstance(params,dict): raise FoundryError(f"params on {nid} must be an object")
        for key,value in params.items():
            if isinstance(value,(int,float)) and not isinstance(value,bool): _finite(value,f"{nid}.{key}")
    for nid,deps in graph.items():
        if any(dep not in ids for dep in deps): raise FoundryError(f"unknown dependency on {nid}")
    # Iterative Kahn topological check avoids Python recursion limits on imported graphs.
    indegree={n:len(deps) for n,deps in graph.items()}
    dependents={n:[] for n in graph}
    for node_id,deps in graph.items():
        for dep in deps: dependents[dep].append(node_id)
    ready=[n for n,count in indegree.items() if count==0]
    visited_count=0
    while ready:
        current=ready.pop(); visited_count+=1
        for child in dependents[current]:
            indegree[child]-=1
            if indegree[child]==0: ready.append(child)
    if visited_count != len(graph): raise FoundryError("dependency cycle detected")
    return {"valid":True,"node_count":len(nodes),"schema":SCHEMA_VERSION}

class Foundry:
    """Build deterministic project graphs from a text/numeric seed and recipe ID."""
    def __init__(self, seed, recipe_id="hybrid-06"):
        if isinstance(seed,(int,float)) and not isinstance(seed,bool):
            if not math.isfinite(float(seed)): raise FoundryError("numeric seed must be finite")
            seed=format(float(seed),".17g")
        if not isinstance(seed,str) or not seed or len(seed)>MAX_SEED_CHARS: raise FoundryError("seed must be 1..512 characters")
        self.seed=seed; self.recipe=get_recipe(recipe_id)
    def build(self, title=None, domains=None):
        r=self.recipe; chosen=list(domains or r["domains"])
        if not chosen or any(d not in {"audio","video","game"} for d in chosen): raise FoundryError("domains must be audio, video and/or game")
        root="seed-root"; nodes=[{"id":root,"kind":"seed","depends_on":[],"params":{"algorithm":"blake2b-256","seed_digest":_digest(self.seed)}}]
        for domain in chosen:
            idx=len(nodes); nid=f"{domain}-main"
            u=lambda k: _unit(self.seed,r["id"],domain+":"+k)
            params={"recipe_id":r["id"],"style":r["name"],"complexity":r["complexity"],
              "tempo_bpm":round(r["tempo_range"][0]+u("tempo")*(r["tempo_range"][1]-r["tempo_range"][0]),3),
              "phase":round(u("phase")*math.tau,9),"density":round(0.1+u("density")*0.85,6),
              "motion_scale":round(r["motion_scale"]*(0.5+u("motion")),6),"palette_hue":(r["palette_index"]+round(u("hue")*90))%360,
              "operators":r["operators"]}
            nodes.append({"id":nid,"kind":domain,"depends_on":[root],"params":params})
        # A shared edit/conform node makes cross-domain timing explicit.
        nodes.append({"id":"timeline-conform","kind":"edit","depends_on":[f"{d}-main" for d in chosen],"params":{"clock":"seeded-beat-grid","bar_count":16,"frame_rate":24}})
        project={"schema":SCHEMA_VERSION,"title":title or f"{r['name']} · {self.seed[:24]}","seed":self.seed,
          "recipe":{"id":r["id"],"name":r["name"],"category":r["category"]},"domains":chosen,
          "nodes":nodes,"settings":{"deterministic":True,"randomness":"hash-derived","master_clock":"musical-bars"}}
        validate_project(project); return project

def make_manifest(project, app_version="unknown"):
    validate_project(project)
    canonical=json.dumps(project,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
    return {"manifest_schema":"1.0","project_sha256":hashlib.sha256(canonical.encode()).hexdigest(),
      "seed_digest":_digest(project["seed"]),"recipe_id":project["recipe"]["id"],
      "node_count":len(project["nodes"]),"domains":list(project["domains"]),
      "app_version":str(app_version),"generator":"Fractal Media Foundry 1.0",
      "python":platform.python_version(),"platform":platform.system(),
      "created_utc":"reproducible-build-time-omitted"}
