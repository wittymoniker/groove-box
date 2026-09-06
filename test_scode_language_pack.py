from pathlib import Path
import tempfile, json
from scode.language_pack import load_language_pack, teach_numeral, teach, validate_language_pack
P=Path("scode_language/language_pack.json")
def test_default_pack_valid():
    p=load_language_pack(P)
    assert p["numerals"]["base"]==16
    assert len(p["numerals"]["canonical_symbols"])==16
def test_teach_word_preserves_semantics():
    p=load_language_pack(P)
    q=teach(p,"keywords","seed","SOURCEWORD")
    assert q["keywords"]["seed"]=="SOURCEWORD"
    assert validate_language_pack(q)
def test_teach_numeral_rejects_collision():
    p=load_language_pack(P)
    try:
        teach_numeral(p,10,"0",["a"])
    except ValueError:
        return
    raise AssertionError("collision should fail")
