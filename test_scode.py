from decimal import Decimal
from scode.numerals import NumeralProfile,parse_number,format_number
from scode.parser import parse_program

def test_native_base16():
    assert parse_number('10')==16
    assert parse_number('FF')==255
    assert parse_number('1.A')==Decimal('1.625')

def test_custom_symbol_keyboard_roundtrip():
    glyphs=tuple('0123456789')+('α','β','γ','δ','ε','ζ')
    p=NumeralProfile(glyphs,tuple('0123456789abcdef'),'test')
    assert p.keyboard_to_symbols('1af')=='1αζ'
    assert parse_number('1αζ',p)==0x1AF

def test_program_parses():
    p=parse_program('studio X {\n permit studio.launch\n}\n')
    assert p.nodes[0].kind=='studio' and p.nodes[0].children[0].name=='studio.launch'

def test_stable_ir_hash():
    from scode.compiler import compile_text
    text='studio X {\n setting radix 10\n}\n'  # sCode literal 10 means hex 0x10 when evaluated
    ir1,h1=compile_text(text); ir2,h2=compile_text(text)
    assert h1==h2 and ir1==ir2

def test_agent_denies_unknown_and_bypass():
    from scode.agent import AgentPolicy
    p=AgentPolicy()
    assert p.decision('model.infer')=='allow'
    assert p.decision('permission.bypass')=='deny'
    assert p.decision('totally.unknown')=='deny'
