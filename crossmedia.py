"""Adapter registry and reproducible Foundry-to-media bundle contracts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable
import copy, hashlib, json

class AdapterError(ValueError): pass

@dataclass(frozen=True)
class Adapter:
    domain: str
    node_kind: str
    adapter_id: str
    version: str
    capabilities: tuple[str,...]
    translate: Callable[[dict[str,Any]],dict[str,Any]]

class AdapterRegistry:
    def __init__(self): self._items={}
    def register(self, adapter: Adapter):
        key=(adapter.domain,adapter.node_kind)
        if key in self._items: raise AdapterError(f"adapter already registered: {key}")
        if adapter.domain not in {"audio","video","game"} or not adapter.adapter_id or not adapter.version: raise AdapterError("invalid adapter identity")
        self._items[key]=adapter
    def get(self, domain, node_kind): return self._items.get((domain,node_kind))
    def describe(self):
        return [{"domain":a.domain,"node_kind":a.node_kind,"adapter_id":a.adapter_id,"version":a.version,"capabilities":list(a.capabilities)} for a in sorted(self._items.values(),key=lambda x:(x.domain,x.node_kind))]

class FoundryAdapter:
    """Converts validated Foundry graph nodes into explicit engine-neutral job specs."""
    DOMAIN_KINDS={"audio":"audio","video":"video","game":"game"}
    def __init__(self, registry: AdapterRegistry): self.registry=registry
    def compile(self, project: dict[str,Any]):
        from fractal_foundry.engine import validate_project, make_manifest
        validate_project(project); manifest=make_manifest(project)
        jobs=[]; missing=[]
        for node in project["nodes"]:
            domain=node.get("kind")
            if domain not in self.DOMAIN_KINDS: continue
            adapter=self.registry.get(domain,domain)
            if adapter is None:
                missing.append({"node_id":node["id"],"domain":domain,"reason":"no renderer adapter registered"}); continue
            translated=adapter.translate(copy.deepcopy(node))
            if not isinstance(translated,dict): raise AdapterError("adapter must return a job object")
            jobs.append({"node_id":node["id"],"domain":domain,"adapter_id":adapter.adapter_id,"adapter_version":adapter.version,"job":translated})
        return {"manifest":manifest,"jobs":jobs,"unresolved":missing,"complete":not missing}

def _generic_translate(node):
    params=node.get("params",{})
    return {"operation":"prepare-domain-project","parameters":copy.deepcopy(params),"source_node":node["id"]}

def build_media_bundle(seed, recipe_id="hybrid-06", title=None, domains=("audio","video","game")):
    """Build linked deterministic project contracts; renderer work is queued only by adapters."""
    from fractal_foundry import Foundry, make_manifest
    project=Foundry(seed,recipe_id).build(title=title,domains=list(domains))
    manifest=make_manifest(project)
    registry=AdapterRegistry()
    for domain in ("audio","video","game"):
        registry.register(Adapter(domain,domain,f"builtin.{domain}.contract","1.0.0",("deterministic-project-spec",),_generic_translate))
    compiled=FoundryAdapter(registry).compile(project)
    bundle={"schema":"fractal-media-bundle/1.0","project":project,"manifest":manifest,
            "adapter_registry":registry.describe(),"compiled_jobs":compiled["jobs"],
            "unresolved":compiled["unresolved"],"renderer_execution":"not-started",
            "capabilities":{"shared_seed":True,"shared_fingerprint":True,"audio_video_game_links":True,
                            "renderers_executed":False,"external_codec_required":True}}
    canonical=json.dumps(bundle,sort_keys=True,separators=(",",":"),allow_nan=False)
    bundle["bundle_sha256"]=hashlib.sha256(canonical.encode()).hexdigest()
    return bundle
