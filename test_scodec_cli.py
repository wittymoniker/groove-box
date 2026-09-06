from pathlib import Path
import json,subprocess,sys
HERE=Path(__file__).resolve().parent
def run(*a):
    return subprocess.run([sys.executable,str(HERE/"scodec.py"),*a],cwd=HERE,text=True,capture_output=True)
def test_deterministic_hash(tmp_path):
    p=tmp_path/"a.scode"; p.write_text("seed A\n",encoding="utf-8")
    a=run("hash",str(p)); b=run("hash",str(p))
    assert a.returncode==0 and a.stdout==b.stdout
def test_compile_emits_radix16(tmp_path):
    p=tmp_path/"a.scode"; o=tmp_path/"a.sir"; p.write_text("seed A\n",encoding="utf-8")
    r=run("compile",str(p),"-o",str(o))
    assert r.returncode==0
    d=json.loads(o.read_text())
    assert d["radix"]==16 and d["source_language"]=="sCode"
def test_bad_block_fails(tmp_path):
    p=tmp_path/"bad.scode"; p.write_text("field x {\n",encoding="utf-8")
    assert run("check",str(p)).returncode != 0
def test_groovebox_compiles():
    r=run("check",str(HERE/"Groovebox.scode"))
    assert r.returncode==0
