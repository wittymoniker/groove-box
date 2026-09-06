#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from scode.compiler import compile_file,write_ir,validate_file
from scode.knowledge import search_knowledge
from scode.theorem_solver import affine_candidate, modular_candidate, transition_candidate, meum_logic_candidate

def build_parser():
    ap=argparse.ArgumentParser(prog="scodec",description="sCode compiler")
    ap.add_argument("--version",action="version",version="scodec 0.3.0")
    sub=ap.add_subparsers(dest="cmd",required=True)
    c=sub.add_parser("compile"); c.add_argument("source"); c.add_argument("-o","--output")
    v=sub.add_parser("check"); v.add_argument("source")
    i=sub.add_parser("inspect"); i.add_argument("source")
    h=sub.add_parser("hash"); h.add_argument("source")
    k=sub.add_parser("know",help="search bundled programmer knowledgebase"); k.add_argument("query"); k.add_argument("--limit",type=int,default=8)
    d=sub.add_parser("devise",help="generate theorem-aware code candidates")
    ds=d.add_subparsers(dest="devise_kind",required=True)
    da=ds.add_parser("affine"); da.add_argument("--x",type=float,required=True); da.add_argument("--a",type=float,required=True); da.add_argument("--b",type=float,required=True); da.add_argument("--steps",type=int,required=True)
    dm=ds.add_parser("modular"); dm.add_argument("--x",type=int,required=True); dm.add_argument("--step",type=int,required=True); dm.add_argument("--steps",type=int,required=True); dm.add_argument("--modulus",type=int,required=True)
    dt=ds.add_parser("transition"); dt.add_argument("--start",required=True); dt.add_argument("--steps",type=int,required=True); dt.add_argument("--table",required=True,help="A:B,B:C,C:B")
    dg=ds.add_parser("meum"); dg.add_argument("--operation",default="canonical_mix")
    return ap

def main(argv=None):
    a=build_parser().parse_args(argv)
    try:
        if a.cmd=="know":
            rows=search_knowledge(a.query,limit=a.limit)
            if not rows:
                print("No matching knowledge entries."); return 2
            for r in rows:
                print(f"[{r['category']}] {r['title']}")
                print(f"  {r['summary']}")
                print(f"  sCode: {r['scode_strategy']}")
            return 0
        if a.cmd=="devise":
            if a.devise_kind=="affine": out=affine_candidate(a.x,a.a,a.b,a.steps)
            elif a.devise_kind=="modular": out=modular_candidate(a.x,a.step,a.steps,a.modulus)
            elif a.devise_kind=="transition":
                table={}
                for pair in a.table.split(','):
                    left,right=pair.split(':',1); table[left.strip()]=right.strip()
                out=transition_candidate(table,a.start,a.steps)
            else: out=meum_logic_candidate(a.operation)
            print(json.dumps({k:v for k,v in out.items() if k!='scode'},indent=2,sort_keys=True,default=str))
            print("\n--- generated sCode ---")
            print(out['scode'],end='')
            return 0
        if a.cmd=="check":
            validate_file(a.source); print(f"{a.source}: valid sCode"); return 0
        ir=compile_file(a.source)
        if a.cmd=="inspect":
            print(json.dumps(ir,sort_keys=True,indent=2,ensure_ascii=False)); return 0
        if a.cmd=="hash":
            print(ir["sha256"]); return 0
        out=Path(a.output) if a.output else Path(a.source).with_suffix(".sir")
        write_ir(ir,out)
        print(f"compiled {a.source} -> {out}")
        print(f"sIR sha256 {ir['sha256']}")
        return 0
    except (SyntaxError,ValueError,OSError) as exc:
        print(f"scodec: error: {exc}",file=sys.stderr); return 1

if __name__=="__main__":
    raise SystemExit(main())
