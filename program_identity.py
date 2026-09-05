from __future__ import annotations
import ast, hashlib, json, os, zipfile
from pathlib import Path
from typing import Any, Dict

FORMAT = 'MathematiciansGrooveboxProgramIdentity'
VERSION = 1

class _Normalizer(ast.NodeTransformer):
    def visit_Module(self, node):
        node = self.generic_visit(node)
        node.body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(getattr(n,'value',None), ast.Constant) and isinstance(n.value.value, str))]
        return node
    def visit_FunctionDef(self, node):
        node = self.generic_visit(node)
        node.body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(getattr(n,'value',None), ast.Constant) and isinstance(n.value.value, str))]
        return node
    visit_AsyncFunctionDef = visit_FunctionDef
    def visit_ClassDef(self, node):
        node = self.generic_visit(node)
        node.body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(getattr(n,'value',None), ast.Constant) and isinstance(n.value.value, str))]
        return node

def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def normalized_python_bytes(data: bytes) -> bytes:
    text = data.decode('utf-8', errors='replace')
    tree = ast.parse(text)
    tree = _Normalizer().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.dump(tree, annotate_fields=True, include_attributes=False).encode('utf-8')

def identify_python(path: str) -> Dict[str, Any]:
    p = Path(path); raw = p.read_bytes()
    try:
        norm = normalized_python_bytes(raw)
        semantic = _sha(norm)
        method = 'python-ast-v1'
    except Exception:
        semantic = _sha(raw); method = 'bytes-v1'
    return {'format':FORMAT,'version':VERSION,'kind':'python','path':str(p.resolve()),'program_id':'PGM-'+semantic[:24].upper(),'semantic_sha256':semantic,'source_sha256':_sha(raw),'method':method,'size':len(raw)}

def identify_zip(path: str) -> Dict[str, Any]:
    p=Path(path); raw=p.read_bytes(); members=[]
    with zipfile.ZipFile(p,'r') as z:
        for name in sorted(z.namelist(), key=str.lower):
            if name.endswith('/'): continue
            data=z.read(name)
            base=os.path.basename(name).lower()
            if base.endswith('.py'):
                try: h=_sha(normalized_python_bytes(data)); mode='py-ast'
                except Exception: h=_sha(data); mode='bytes'
            else:
                h=_sha(data); mode='bytes'
            # Ignore member path for semantic package identity; keep filename + content.
            members.append((base, mode, h))
    semantic=_sha(json.dumps(members,separators=(',',':'),sort_keys=False).encode())
    return {'format':FORMAT,'version':VERSION,'kind':'zip','path':str(p.resolve()),'program_id':'PGM-'+semantic[:24].upper(),'semantic_sha256':semantic,'source_sha256':_sha(raw),'method':'zip-semantic-v1','member_count':len(members),'size':len(raw)}

def identify(path: str) -> Dict[str, Any]:
    s=str(path)
    if s.lower().endswith('.py'): return identify_python(s)
    if s.lower().endswith('.zip'): return identify_zip(s)
    p=Path(s); raw=p.read_bytes(); h=_sha(raw)
    return {'format':FORMAT,'version':VERSION,'kind':'file','path':str(p.resolve()),'program_id':'PGM-'+h[:24].upper(),'semantic_sha256':h,'source_sha256':h,'method':'bytes-v1','size':len(raw)}
