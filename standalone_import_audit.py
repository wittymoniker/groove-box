#!/usr/bin/env python3
"""Classify every Python import in the Groovebox tree for standalone builds."""
from __future__ import annotations
import ast, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
STDLIB=set(getattr(sys,'stdlib_module_names',()))
LOCAL={p.stem for p in ROOT.glob('*.py') if p.stem.isidentifier()} | {p.name for p in ROOT.iterdir() if p.is_dir() and p.name.isidentifier() and (p/'__init__.py').exists()}
BUNDLED={'PyQt6','numpy','sounddevice','PIL'}
OPTIONAL={'juliacall','mido'}

def scan():
 out=[]
 for p in sorted(ROOT.glob('*.py')):
  if '.pre_' in p.name or p.name.endswith('.pre.py'): continue
  try: tree=ast.parse(p.read_text(encoding='utf-8',errors='ignore'))
  except Exception: continue
  for n in ast.walk(tree):
   names=[]
   if isinstance(n,ast.Import): names=[a.name for a in n.names]
   elif isinstance(n,ast.ImportFrom) and n.module: names=[n.module]
   for name in names:
    top=name.split('.')[0]
    if top in STDLIB or top=='__future__': kind='stdlib/os'
    elif top in LOCAL: kind='local'
    elif top in BUNDLED: kind='bundled-runtime'
    elif top in OPTIONAL: kind='optional'
    else: kind='review'
    out.append({'file':p.name,'line':getattr(n,'lineno',0),'import':name,'class':kind})
 return out
if __name__=='__main__':
 rows=scan(); print(json.dumps(rows,indent=2));
 bad=[r for r in rows if r['class']=='review']
 raise SystemExit(1 if bad else 0)
