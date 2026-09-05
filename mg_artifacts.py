from __future__ import annotations
import copy, hashlib, json, math, os, time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

FORMAT='MathematiciansGrooveboxMG'
VERSION=1
KINDS=('project','synth','profile')
EXTENSIONS={'project':'.MGproject','synth':'.MGsynth','profile':'.MGprofile'}

TRANSIENT_KEYS={'analytics','artifact_id','integrity_sha256','last_used','use_count','related_cache'}

def _canon(obj):
    if isinstance(obj, dict): return {str(k):_canon(v) for k,v in sorted(obj.items(), key=lambda kv:str(kv[0])) if str(k) not in TRANSIENT_KEYS}
    if isinstance(obj, (list,tuple)): return [_canon(x) for x in obj]
    if isinstance(obj, float):
        if math.isnan(obj): return 'NaN'
        if math.isinf(obj): return 'Infinity' if obj>0 else '-Infinity'
        return round(obj, 12)
    if isinstance(obj, (str,int,bool)) or obj is None: return obj
    return str(obj)

def _digest(obj): return hashlib.sha256(json.dumps(_canon(obj),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')).hexdigest()

def artifact_id(kind:str, payload:Any)->str:
    h=_digest({'kind':kind,'payload':payload})
    return f'MG-{kind.upper()}-{h[:20].upper()}'

def make(kind:str,payload:Any,*,program_id:str='',composition_id:str='',title:str='',tags:Optional[List[str]]=None,analytics:Optional[Dict[str,Any]]=None)->Dict[str,Any]:
    kind=str(kind).lower()
    if kind not in KINDS: raise ValueError('Unknown .MG kind')
    created=time.time()
    doc={'format':FORMAT,'version':VERSION,'kind':kind,'title':title or kind.title(),'payload':copy.deepcopy(payload),'provenance':{'program_id':program_id or None,'composition_id':composition_id or None},'tags':list(tags or []),'created_at':created,'analytics':copy.deepcopy(analytics or {'use_count':0,'load_count':0,'save_count':1,'first_used':None,'last_used':None,'companions':{},'outcomes':{}})}
    doc['artifact_id']=artifact_id(kind,doc['payload'])
    doc['integrity_sha256']=_digest({'format':doc['format'],'version':doc['version'],'kind':kind,'artifact_id':doc['artifact_id'],'payload':doc['payload'],'provenance':doc['provenance']})
    return doc

def save(path:str,doc:Dict[str,Any])->str:
    p=Path(path); kind=str(doc.get('kind','')).lower(); ext=EXTENSIONS.get(kind,'.MG')
    if p.suffix.lower() not in {e.lower() for e in EXTENSIONS.values()} and not str(p).lower().endswith('.mg'):
        p=Path(str(p)+ext)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(doc,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    return str(p.resolve())

def load(path:str,expected_kind:Optional[str]=None,record_use:bool=True)->Dict[str,Any]:
    p=Path(path); doc=json.loads(p.read_text(encoding='utf-8'))
    if doc.get('format')!=FORMAT: raise ValueError('Not a Mathematician\'s Groovebox .MG artifact')
    kind=str(doc.get('kind','')).lower()
    if expected_kind and kind!=str(expected_kind).lower(): raise ValueError(f'Expected .MG {expected_kind}, got {kind}')
    if doc.get('artifact_id')!=artifact_id(kind,doc.get('payload')): raise ValueError('.MG artifact identity check failed')
    if record_use:
        a=doc.setdefault('analytics',{}); now=time.time(); a['load_count']=int(a.get('load_count',0))+1; a['use_count']=int(a.get('use_count',0))+1; a['first_used']=a.get('first_used') or now; a['last_used']=now
        try: p.write_text(json.dumps(doc,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
        except Exception: pass
    return doc

def record_companion(path_a:str,path_b:str,weight:float=1.0):
    for src,other in ((path_a,path_b),(path_b,path_a)):
        try:
            doc=load(src,record_use=False); a=doc.setdefault('analytics',{}); c=a.setdefault('companions',{}); key=os.path.basename(other); c[key]=float(c.get(key,0.0))+float(weight); Path(src).write_text(json.dumps(doc,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
        except Exception: pass

def _flatten_numbers(obj,prefix='',out=None):
    out={} if out is None else out
    if isinstance(obj,dict):
        for k,v in obj.items(): _flatten_numbers(v,prefix+'/'+str(k),out)
    elif isinstance(obj,(list,tuple)):
        for i,v in enumerate(obj[:256]): _flatten_numbers(v,prefix+f'/{i}',out)
    elif isinstance(obj,(int,float)) and not isinstance(obj,bool) and math.isfinite(float(obj)): out[prefix]=float(obj)
    return out

def _token_set(doc):
    s=set(str(x).lower() for x in doc.get('tags',[]) if x)
    prov=doc.get('provenance',{}) or {}
    for k in ('program_id','composition_id'):
        if prov.get(k): s.add(str(prov[k]).lower())
    return s

def relationship_score(a:Dict[str,Any],b:Dict[str,Any])->float:
    score=0.0
    pa,pb=a.get('provenance',{}) or {},b.get('provenance',{}) or {}
    if pa.get('program_id') and pa.get('program_id')==pb.get('program_id'): score+=0.24
    if pa.get('composition_id') and pa.get('composition_id')==pb.get('composition_id'): score+=0.28
    ta,tb=_token_set(a),_token_set(b)
    if ta or tb: score+=0.12*(len(ta&tb)/max(1,len(ta|tb)))
    na,nb=_flatten_numbers(a.get('payload')),_flatten_numbers(b.get('payload'))
    shared=set(na)&set(nb)
    if shared:
        sims=[]
        for k in list(shared)[:128]:
            x,y=na[k],nb[k]; sims.append(1.0/(1.0+abs(x-y)/(1.0+abs(x)+abs(y))))
        score+=0.26*(sum(sims)/len(sims))
    companions=(a.get('analytics',{}) or {}).get('companions',{}) or {}
    bname=str(b.get('_path_name',''))
    if bname and bname in companions: score+=min(0.10,0.02*float(companions[bname]))
    if a.get('kind')!=b.get('kind'): score+=0.04
    return max(0.0,min(1.0,score))

def find_related(target_path:str,roots:Iterable[str],limit:int=12)->List[Dict[str,Any]]:
    target=load(target_path,record_use=False); results=[]
    for root in roots:
        if not root or not os.path.isdir(root): continue
        for base,_,files in os.walk(root):
            for fn in files:
                low=fn.lower()
                if not (low.endswith('.mgproject') or low.endswith('.mgsynth') or low.endswith('.mgprofile') or low.endswith('.mg')): continue
                p=os.path.join(base,fn)
                if os.path.abspath(p)==os.path.abspath(target_path): continue
                try:
                    d=load(p,record_use=False); d['_path_name']=fn; score=relationship_score(target,d)
                    results.append({'path':p,'score':score,'kind':d.get('kind'),'artifact_id':d.get('artifact_id'),'title':d.get('title',fn),'analytics':d.get('analytics',{})})
                except Exception: continue
    results.sort(key=lambda x:(-x['score'],x['title'].lower()))
    return results[:max(1,int(limit))]


# HISTORY_MAINTENANCE_2026 ----------------------------------------------------
def _analytics_summary(a):
    a=a or {}; companions=a.get('companions',{}) or {}; outcomes=a.get('outcomes',{}) or {}
    return {
        'use_count': int(a.get('use_count',0) or 0),
        'load_count': int(a.get('load_count',0) or 0),
        'save_count': int(a.get('save_count',0) or 0),
        'first_used': a.get('first_used'), 'last_used': a.get('last_used'),
        'companion_total': float(sum(float(v) for v in companions.values() if isinstance(v,(int,float)))),
        'companion_unique': len(companions), 'outcome_keys': len(outcomes),
    }

def compress_history(path:str, keep_companions:int=24, keep_outcomes:int=32)->Dict[str,Any]:
    """Compress mutable longitudinal analytics without changing Artifact ID."""
    p=Path(path); doc=load(str(p),record_use=False); a=doc.setdefault('analytics',{})
    before=_analytics_summary(a)
    comps=a.get('companions',{}) or {}
    ranked=sorted(comps.items(), key=lambda kv:(-float(kv[1]),str(kv[0])))[:max(0,int(keep_companions))]
    dropped=sum(float(v) for k,v in comps.items() if (k,v) not in ranked and isinstance(v,(int,float)))
    a['companions']={k:v for k,v in ranked}
    if dropped: a['companions_other_weight']=float(a.get('companions_other_weight',0.0))+dropped
    outs=a.get('outcomes',{}) or {}
    if isinstance(outs,dict) and len(outs)>keep_outcomes:
        keys=sorted(outs,key=str)[:max(0,int(keep_outcomes))]
        a['outcomes']={k:outs[k] for k in keys}
        a['outcomes_compressed_count']=int(a.get('outcomes_compressed_count',0))+len(outs)-len(keys)
    a['history_compressed_at']=time.time(); a['history_summary_before']=before
    p.write_text(json.dumps(doc,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    return {'artifact_id':doc.get('artifact_id'),'before':before,'after':_analytics_summary(a)}

def clear_history(path:str, preserve_totals:bool=True)->Dict[str,Any]:
    """Clear mutable use/co-use/outcome history while preserving artifact identity/content."""
    p=Path(path); doc=load(str(p),record_use=False); old=doc.get('analytics',{}) or {}
    totals=_analytics_summary(old) if preserve_totals else {}
    doc['analytics']={'use_count':0,'load_count':0,'save_count':int(old.get('save_count',1) or 1),
                      'first_used':None,'last_used':None,'companions':{},'outcomes':{}}
    if preserve_totals: doc['analytics']['cleared_previous_totals']=totals
    doc['analytics']['history_cleared_at']=time.time()
    p.write_text(json.dumps(doc,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    return {'artifact_id':doc.get('artifact_id'),'cleared':True,'preserved_totals':totals}

def compress_history_tree(roots:Iterable[str], keep_companions:int=24)->Dict[str,int]:
    done=failed=0
    for root in roots:
        if not root or not os.path.isdir(root): continue
        for base,_,files in os.walk(root):
            for fn in files:
                if not fn.lower().endswith(('.mgproject','.mgsynth','.mgprofile','.mg')): continue
                try: compress_history(os.path.join(base,fn),keep_companions); done+=1
                except Exception: failed+=1
    return {'compressed':done,'failed':failed}


def export_history(path:str, out_path:str, fmt:str='json')->str:
    """Export provenance + mutable analytics without changing the source artifact.

    Supported formats: JSON, CSV, HTML.  Export is read-only and therefore
    cannot alter Artifact ID, payload, use counters, or timestamps.
    """
    import csv, html
    src=load(path,record_use=False)
    fmt=str(fmt or 'json').lower().lstrip('.')
    out=Path(out_path); out.parent.mkdir(parents=True,exist_ok=True)
    a=copy.deepcopy(src.get('analytics',{}) or {})
    prov=copy.deepcopy(src.get('provenance',{}) or {})
    report={
        'format':'MathematiciansGrooveboxHistoryExport','version':1,
        'source_path':str(Path(path).resolve()),'artifact_id':src.get('artifact_id'),
        'kind':src.get('kind'),'title':src.get('title'),'tags':src.get('tags',[]),
        'program_id':prov.get('program_id'),'composition_id':prov.get('composition_id'),
        'created_at':src.get('created_at'),'exported_at':time.time(),'analytics':a,
        'summary':_analytics_summary(a),
    }
    if fmt=='json':
        out.write_text(json.dumps(report,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    elif fmt=='csv':
        rows=[]
        for k,v in report.items():
            if k=='analytics': continue
            rows.append(('meta',k,json.dumps(v,ensure_ascii=False,default=str) if isinstance(v,(dict,list)) else v))
        for k,v in a.items():
            if isinstance(v,dict):
                for sk,sv in v.items(): rows.append((k,sk,sv))
            else: rows.append(('analytics',k,v))
        with out.open('w',encoding='utf-8',newline='') as f:
            w=csv.writer(f); w.writerow(['section','key','value']); w.writerows(rows)
    elif fmt in ('html','htm'):
        esc=lambda x: html.escape(str(x))
        def table(d):
            return ''.join(f'<tr><th>{esc(k)}</th><td><pre>{esc(json.dumps(v,ensure_ascii=False,indent=2,default=str) if isinstance(v,(dict,list)) else v)}</pre></td></tr>' for k,v in d.items())
        out.write_text('<!doctype html><meta charset="utf-8"><title>.MG History Export</title>'
                       '<style>body{font-family:system-ui;background:#101318;color:#e8eef5;max-width:1100px;margin:auto;padding:24px}table{border-collapse:collapse;width:100%}th,td{border:1px solid #374151;padding:8px;text-align:left;vertical-align:top}pre{white-space:pre-wrap;margin:0}</style>'
                       f'<h1>.MG History Export</h1><h2>{esc(report.get("title"))}</h2><table>{table({k:v for k,v in report.items() if k!="analytics"})}</table><h2>Analytics</h2><table>{table(a)}</table>',encoding='utf-8')
    else: raise ValueError('History export format must be json, csv, or html')
    return str(out.resolve())
